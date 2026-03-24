import os
import shutil
from datetime import datetime

import dlt
import psycopg2
from langchain_core.messages import SystemMessage
from loguru import logger

import env
import workflow_config
from rag import custom_prompt
from rag.ollama_client import call_ollama
from utils.config_by_path import ConfigByPath

# Cập nhật import Google Drive
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
    upload_to_drive,
)

# Cập nhật import Hash Helper
from utils.hash_helper import get_existing_drive_id_from_db, get_existing_hash_from_db
from utils.workflow_helper import (
    document_state_resource,
    fetch_and_lock_pending_tasks,
    get_workflow_item_counts_via_pipeline,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def get_context_from_ollama(summary_text, chunk_text, max_retries=3):
    messages = [
        SystemMessage(
            content=custom_prompt.CONTEXTUALIZER_PROMPT.format(
                summary=summary_text, chunk=chunk_text
            )
        )
    ]
    return call_ollama(messages, max_retries=max_retries, stream=True)


@dlt.resource(
    name="document_context",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_context_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)
    except Exception as e:
        logger.error(f"Lỗi khởi tạo kết nối Database/Drive: {e}")
        return

    try:
        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=None,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có tài liệu nào cần tạo ngữ cảnh (contextualizing).")
            return

        for item_id in pending_item_ids:
            item_workspace = os.path.join(PATH_FOLDER_OUTPUT, f"workspace_{item_id}")
            zip_base_output_path = os.path.join(
                PATH_FOLDER_OUTPUT, f"contextualized_{item_id}"
            )
            final_zip_path = f"{zip_base_output_path}.zip"

            try:
                # 1. Lấy Drive ID của Summary & Chunks từ Database
                summary_drive_id = get_existing_drive_id_from_db(
                    conn, "document_summary", item_id, "drive_id"
                )
                chunk_drive_id = get_existing_drive_id_from_db(
                    conn, "document_chunking", item_id, "drive_id"
                )

                if not summary_drive_id or not chunk_drive_id:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Thiếu dữ liệu Summary hoặc Chunks (không có drive_id)."
                    )
                    error_item_ids.append(item_id)
                    continue

                # 2. Lấy mã MD5 hiện tại của cả 2 file trực tiếp từ Google Drive API
                current_summary_md5 = get_drive_file_md5(
                    drive_service, summary_drive_id
                )
                current_chunk_md5 = get_drive_file_md5(drive_service, chunk_drive_id)

                if not current_summary_md5 or not current_chunk_md5:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Không lấy được MD5 từ Google Drive."
                    )
                    error_item_ids.append(item_id)
                    continue

                # 3. Truy vấn lịch sử từ bảng document_context (lấy MD5 cũ)
                old_summary_md5, old_chunk_md5 = get_existing_hash_from_db(
                    conn, "document_context", item_id, "summary_md5", "chunk_md5"
                )

                # 4. TRẠM GÁC: Skip nếu cả Tóm tắt và Chunks đều không có thay đổi
                if (
                    old_summary_md5 == current_summary_md5
                    and old_chunk_md5 == current_chunk_md5
                ):
                    logger.info(
                        f"⏭️ Bỏ qua {item_id}: Cả Summary và Chunks không đổi, không cần sinh lại ngữ cảnh."
                    )
                    success_item_ids.append(item_id)
                    continue

                # 5. TIẾN HÀNH: Tải dữ liệu Tóm tắt
                logger.info(f"📥 Đang tải dữ liệu tóm tắt và chunks cho: {item_id}")
                summary_bytes = download_from_drive(drive_service, summary_drive_id)
                summary_text = summary_bytes.decode("utf-8")

                # 6. Thiết lập workspace, tải và giải nén Chunks Zip
                extract_dir = os.path.join(item_workspace, "raw_chunks")
                contextualized_dir = os.path.join(
                    item_workspace, "contextualized_chunks"
                )

                os.makedirs(extract_dir, exist_ok=True)
                os.makedirs(contextualized_dir, exist_ok=True)

                zip_local_path = os.path.join(item_workspace, f"raw_{item_id}.zip")
                zip_bytes = download_from_drive(drive_service, chunk_drive_id)

                with open(zip_local_path, "wb") as f:
                    f.write(zip_bytes)

                shutil.unpack_archive(zip_local_path, extract_dir)

                # 7. Duyệt qua từng chunk và tạo Context bằng Ollama
                chunk_files = [f for f in os.listdir(extract_dir) if f.endswith(".md")]
                logger.info(
                    f"🔍 Bắt đầu tạo ngữ cảnh cho {len(chunk_files)} đoạn (chunks)..."
                )

                for chunk_filename in chunk_files:
                    raw_chunk_path = os.path.join(extract_dir, chunk_filename)
                    contextualized_chunk_path = os.path.join(
                        contextualized_dir, chunk_filename
                    )

                    with open(raw_chunk_path, "r", encoding="utf-8") as f:
                        chunk_content = f.read().strip()

                    if not chunk_content:
                        continue

                    # Gọi AI tạo ngữ cảnh
                    logger.info(f"⏳ Đang sinh ngữ cảnh cho {chunk_filename}...")
                    ai_context = get_context_from_ollama(summary_text, chunk_content)

                    # Trộn ngữ cảnh vào đầu đoạn văn
                    if ai_context:
                        final_chunk_content = f"BỐI CẢNH (CONTEXT):\n{ai_context}\n\nNỘI DUNG (CONTENT):\n{chunk_content}"
                    else:
                        logger.warning(
                            f"⚠️ Tạo ngữ cảnh thất bại cho {chunk_filename}, giữ nguyên nội dung gốc."
                        )
                        final_chunk_content = chunk_content

                    with open(contextualized_chunk_path, "w", encoding="utf-8") as f:
                        f.write(final_chunk_content)

                # 8. Đóng gói thư mục contextualized thành file ZIP mới
                shutil.make_archive(zip_base_output_path, "zip", contextualized_dir)

                # 9. Upload ZIP lên Google Drive
                logger.info(f"☁️ Đang tải file Context Zip lên Google Drive...")
                new_drive_id = upload_to_drive(
                    drive_service, final_zip_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                if not new_drive_id:
                    logger.error(f"❌ Upload file Context Zip thất bại cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # 10. THÀNH CÔNG: Yield dữ liệu mới (lưu 2 input hash)
                logger.success(f"✅ Đã xử lý ngữ cảnh thành công cho {item_id}")
                success_item_ids.append(item_id)

                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "drive_id": new_drive_id,
                    "summary_md5": current_summary_md5,  # Lưu lại để làm trạm gác lần sau
                    "chunk_md5": current_chunk_md5,  # Lưu lại để làm trạm gác lần sau
                    # KHÔNG còn context_zip_hash nữa
                }

            except Exception as e:
                logger.error(f"💥 Lỗi tại item {item_id}: {e}")
                error_item_ids.append(item_id)

            finally:
                # Đảm bảo rác workspace và zip luôn được dọn dẹp sạch sẽ
                if os.path.exists(item_workspace):
                    shutil.rmtree(item_workspace, ignore_errors=True)
                if os.path.exists(final_zip_path):
                    os.remove(final_zip_path)

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

    info = pipeline.run(document_context_resource(success_item_ids, error_item_ids))
    logger.info(f"Kết quả pipeline: {info}")

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
                workflow_id=workflow_config.STEP_LOAD_DOCUMENT_LIST.id,
                item_ids=error_item_ids,
                start_time=start_time,
                end_time=datetime.now(),
            )
        )

    get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
