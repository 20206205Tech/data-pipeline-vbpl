import os
from datetime import datetime

import dlt
import psycopg2
from langchain_core.messages import SystemMessage
from loguru import logger

import env
from rag.llm import invoke_llm_chain
from rag.prompt import summary_prompt
from utils.config_by_path import ConfigByPath
from utils.document_helper import get_document_statuses_from_db, is_document_invalid
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
    upload_to_drive,
)
from utils.hash_helper import (
    get_existing_drive_ids_from_db,
    get_existing_hashes_from_db,
)
from utils.workflow_helper import (
    fetch_and_lock_pending_tasks,
    log_error_workflow_state,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def generate_document_summary(text_content):
    messages = [
        SystemMessage(
            content=summary_prompt.SUMMARY_PROMPT.format(document=text_content)
        )
    ]
    return invoke_llm_chain(messages)


@dlt.resource(
    name="document_summary",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_summary_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=40,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có tài liệu nào cần tóm tắt.")
            return

        dict_md_drive_ids = get_existing_drive_ids_from_db(
            conn, "document_markdown", pending_item_ids, "drive_id"
        )

        dict_summary_hashes = get_existing_hashes_from_db(
            conn, "document_summary", pending_item_ids, "md_hash", "drive_id"
        )

        dict_statuses = get_document_statuses_from_db(conn, pending_item_ids)

        for item_id in pending_item_ids:
            try:
                raw_status = dict_statuses.get(str(item_id))
                if is_document_invalid(raw_status):
                    logger.info(
                        f"⏭️ Bỏ qua {item_id}: Văn bản có trạng thái '{raw_status}'."
                    )
                    success_item_ids.append(item_id)
                    continue

                md_drive_id = dict_md_drive_ids.get(str(item_id))

                if not md_drive_id:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Không tìm thấy dữ liệu Markdown."
                    )
                    error_item_ids.append(item_id)
                    continue

                # 2. Gọi API hỏi Google Drive mã MD5 hiện tại của file Markdown này
                current_md_md5 = get_drive_file_md5(drive_service, md_drive_id)

                if not current_md_md5:
                    logger.warning(
                        f"⚠️ Không lấy được MD5 từ Drive cho Markdown của {item_id}"
                    )
                    error_item_ids.append(item_id)
                    continue

                old_md_hash, _ = dict_summary_hashes.get(str(item_id), (None, None))

                # 4. TRẠM GÁC: Skip hoàn toàn nếu Markdown không thay đổi
                if old_md_hash == current_md_md5:
                    logger.info(
                        f"⏭️ Bỏ qua {item_id}: Nội dung Markdown không thay đổi, không cần gọi LLM."
                    )
                    success_item_ids.append(item_id)
                    continue

                logger.info(f"📝 Đang tải và tóm tắt tài liệu: {item_id}")
                md_bytes = download_from_drive(drive_service, md_drive_id)
                md_text = md_bytes.decode("utf-8")

                summary_text = generate_document_summary(md_text)
                if not summary_text:
                    logger.error(f"❌ LLM không trả về kết quả cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # 6. Ghi text tóm tắt ra file local và Upload
                file_name = f"{item_id}.txt"
                file_path = os.path.join(PATH_FOLDER_OUTPUT, file_name)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)

                new_drive_id = upload_to_drive(
                    drive_service, file_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                if not new_drive_id:
                    logger.error(f"❌ Upload file tóm tắt thất bại cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # 7. THÀNH CÔNG: Yield dữ liệu (lưu lại current_md_md5 để dành cho lần sau)
                logger.success(f"✅ Đã cập nhật tóm tắt mới cho {item_id}")
                success_item_ids.append(item_id)

                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "drive_id": new_drive_id,
                    "md_hash": current_md_md5,  # QUAN TRỌNG: Lưu lại hash của file đầu vào
                }

            except Exception as e:
                logger.error(f"💥 Lỗi tại item {item_id}: {e}")
                error_item_ids.append(item_id)

    except Exception as e:
        logger.error(f"Lỗi khởi tạo resource hoặc kết nối DB: {e}")
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

    pipeline.run(document_summary_resource(success_item_ids, error_item_ids))
    # logger.info(f"Kết quả pipeline: {info}")

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

        log_error_workflow_state(pipeline, error_item_ids, start_time)


if __name__ == "__main__":
    main()
