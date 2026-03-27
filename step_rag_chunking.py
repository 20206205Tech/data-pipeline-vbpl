import os
import re
import shutil
from datetime import datetime

import dlt
import psycopg2
from langchain_core.messages import SystemMessage
from loguru import logger

import env
from rag import custom_prompt
from rag.ollama_client import call_ollama
from utils.config_by_path import ConfigByPath
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
    upload_to_drive,
)
from utils.hash_helper import get_existing_drive_id_from_db, get_existing_hash_from_db
from utils.workflow_helper import (
    document_state_resource,
    fetch_and_lock_pending_tasks,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def get_chunking_suggestions_ollama(summary_text, chunked_text, max_retries=3):
    messages = [
        SystemMessage(
            content=custom_prompt.CHUNKING_PROMPT.format(
                summary=summary_text, chunked_text=chunked_text
            )
        )
    ]
    return call_ollama(messages, max_retries=max_retries, stream=True)


def split_text_by_llm_suggestions(chunked_text, llm_response):
    split_after = []
    match = re.search(r"split_after:\s*([\d,\s]+)", llm_response)

    if match:
        raw_numbers = match.group(1)
        split_after = [
            int(x.strip()) for x in raw_numbers.split(",") if x.strip().isdigit()
        ]

    if not split_after:
        clean_text = re.sub(r"<\|(start|end)_chunk_\d+\|>", "", chunked_text)
        return [clean_text.strip()]

    chunk_pattern = r"<\|start_chunk_(\d+)\|>\n(.*?)\n<\|end_chunk_\d+\|>"
    chunks = re.findall(chunk_pattern, chunked_text, re.DOTALL)

    sections = []
    current_section = []

    for chunk_id, chunk_content in chunks:
        current_section.append(chunk_content)
        if int(chunk_id) in split_after:
            sections.append("\n\n".join(current_section).strip())
            current_section = []

    if current_section:
        sections.append("\n\n".join(current_section).strip())

    return sections


def process_and_chunk(summary_text, md_text):
    chunks = re.split(r"(?=\n#|\n\*\*)", md_text)

    processed_chunks = []
    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue
        formatted_chunk = f"<|start_chunk_{i}|>\n{chunk}\n<|end_chunk_{i}|>"
        processed_chunks.append(formatted_chunk)

    final_text = "\n\n".join(processed_chunks)

    logger.info("⏳ Đang gọi Ollama LLM để đánh giá semantic chunking...")
    llm_response = get_chunking_suggestions_ollama(summary_text, final_text)

    if not llm_response:
        logger.error("❌ Không nhận được phản hồi từ Ollama.")
        return []

    logger.info(f"💡 LLM Response: {llm_response.strip()}")
    final_sections = split_text_by_llm_suggestions(final_text, llm_response)

    return final_sections


@dlt.resource(
    name="document_chunking",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_chunking_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=10,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có tài liệu Markdown nào cần phân mảnh.")
            return

        for item_id in pending_item_ids:
            item_folder = os.path.join(PATH_FOLDER_OUTPUT, f"chunk_{item_id}")
            zip_base_path = os.path.join(PATH_FOLDER_OUTPUT, f"chunk_zip_{item_id}")
            zip_file_path = f"{zip_base_path}.zip"

            try:
                # 1. Lấy drive_id của file Markdown từ DB
                md_drive_id = get_existing_drive_id_from_db(
                    conn, "document_markdown", item_id, "drive_id"
                )

                # 2. Lấy drive_id của file Summary từ DB
                summary_drive_id = get_existing_drive_id_from_db(
                    conn, "document_summary", item_id, "drive_id"
                )

                if not md_drive_id or not summary_drive_id:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Thiếu dữ liệu Markdown hoặc Summary (không có drive_id)."
                    )
                    error_item_ids.append(item_id)
                    continue

                # 3. Hỏi API Google Drive mã MD5 hiện tại của file Markdown
                current_md_md5 = get_drive_file_md5(drive_service, md_drive_id)

                if not current_md_md5:
                    logger.warning(
                        f"⚠️ Không lấy được MD5 từ Drive cho Markdown của {item_id}"
                    )
                    error_item_ids.append(item_id)
                    continue

                # 4. Truy vấn lịch sử xử lý Chunking (lấy md_hash cũ)
                old_md_hash, _ = get_existing_hash_from_db(
                    conn, "document_chunking", item_id, "md_hash", "drive_id"
                )

                # 5. TRẠM GÁC: Bỏ qua nếu Markdown không thay đổi
                if old_md_hash == current_md_md5:
                    logger.info(
                        f"⏭️ Bỏ qua {item_id}: Nội dung Markdown không thay đổi, không cần gọi LLM Chunking."
                    )
                    success_item_ids.append(item_id)
                    continue

                # 6. TIẾN HÀNH: Tải file Markdown và Summary từ Google Drive
                logger.info(
                    f"📝 Đang tải dữ liệu Markdown & Summary cho tài liệu: {item_id}"
                )

                md_bytes = download_from_drive(drive_service, md_drive_id)
                md_text = md_bytes.decode("utf-8")

                summary_bytes = download_from_drive(drive_service, summary_drive_id)
                summary_text = summary_bytes.decode("utf-8")

                # 7. Thực hiện Chunking (Gọi LLM)
                final_sections = process_and_chunk(summary_text, md_text)

                if not final_sections:
                    logger.error(f"❌ Quá trình bóc tách chunks thất bại cho {item_id}.")
                    error_item_ids.append(item_id)
                    continue

                # 8. Tạo cấu trúc thư mục và lưu từng file chunk_x.md
                os.makedirs(item_folder, exist_ok=True)

                for idx, section in enumerate(final_sections):
                    chunk_path = os.path.join(item_folder, f"chunk_{idx + 1}.md")
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(section)

                logger.info(
                    f"📁 Đã tạo {len(final_sections)} file chunks trong thư mục: {item_folder}"
                )

                # 9. Nén thư mục thành file ZIP
                shutil.make_archive(zip_base_path, "zip", item_folder)

                # 10. Upload ZIP lên Google Drive
                logger.info(f"☁️ Đang tải file nén lên Google Drive...")
                new_drive_id = upload_to_drive(
                    drive_service, zip_file_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                if not new_drive_id:
                    logger.error(f"❌ Upload file Zip thất bại cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # 11. THÀNH CÔNG: Yield dữ liệu mới
                logger.success(
                    f"✅ Đã xử lý phân mảnh (chunking) thành công cho {item_id} (Drive ID: {new_drive_id})"
                )
                success_item_ids.append(item_id)

                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "drive_id": new_drive_id,
                    "md_hash": current_md_md5,  # QUAN TRỌNG: Lưu lại hash của input
                    # KHÔNG lưu zip_hash nữa
                }

            except Exception as e:
                logger.error(f"💥 Lỗi tại item {item_id}: {e}")
                error_item_ids.append(item_id)

            finally:
                # Dọn dẹp thư mục làm việc dù thành công hay thất bại (tránh rác máy local)
                if os.path.exists(item_folder):
                    shutil.rmtree(item_folder, ignore_errors=True)
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)

    finally:
        if "conn" in locals() and conn:
            conn.close()


def main():
    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )

    success_item_ids = []
    error_item_ids = []
    start_time = datetime.now()

    pipeline.run(document_chunking_resource(success_item_ids, error_item_ids))
    # # logger.info(f"Kết quả pipeline: {info}")

    if success_item_ids:
        log_workflow_state(
            pipeline=pipeline,
            item_ids=success_item_ids,
            start_time=start_time,
            end_time=datetime.now(),
        )
        logger.info(f"Đã xử lý thành công {len(success_item_ids)} items.")

    if error_item_ids:
        logger.error(
            f"Có {len(error_item_ids)} items gặp lỗi và cần thu thập/chạy lại."
        )
        logger.warning(f"Danh sách lỗi: {error_item_ids}")

        pipeline.run(
            document_state_resource(
                workflow_id=0,
                item_ids=error_item_ids,
                start_time=start_time,
                end_time=datetime.now(),
            )
        )

    # get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
