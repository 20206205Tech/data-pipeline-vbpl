import os
from datetime import datetime

import dlt
import psycopg2
from bs4 import BeautifulSoup
from loguru import logger

import env
import workflow_config
from utils.config_by_path import ConfigByPath
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
    upload_to_drive,
)
from utils.hash_helper import calculate_file_md5, get_existing_drive_id_from_db
from utils.workflow_helper import (
    document_state_resource,
    fetch_and_lock_pending_tasks,
    get_workflow_item_counts_via_pipeline,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def extract_clean_content(item_id, html_content):
    try:
        soup = BeautifulSoup(html_content, "lxml")
        content_div = soup.find("div", id="toanvancontent")
        if not content_div:
            return None
        return str(content_div)
    except Exception as e:
        logger.error(f"Lỗi parse nội dung {item_id}: {e}")
        return None


@dlt.resource(
    name="document_content",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_content_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=None,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có dữ liệu mới cần trích xuất nội dung.")
            return

        for item_id in pending_item_ids:
            file_name = f"{item_id}.html"
            file_path = os.path.join(PATH_FOLDER_OUTPUT, file_name)

            try:
                raw_drive_id = get_existing_drive_id_from_db(
                    conn, "document_detail", item_id, "drive_id"
                )

                if not raw_drive_id:
                    logger.warning(f"Bỏ qua {item_id}: Không tìm thấy drive_id gốc.")
                    error_item_ids.append(item_id)
                    continue

                logger.info(f"Đang xử lý nội dung cho: {item_id}")

                # 2. Tải HTML thô từ Drive và trích xuất nội dung
                html_bytes = download_from_drive(drive_service, raw_drive_id)
                html_text = html_bytes.decode("utf-8")

                clean_html = extract_clean_content(item_id, html_text)

                if not clean_html:
                    logger.warning(
                        f"⚠️ Không tìm thấy thẻ div#toanvancontent cho {item_id}"
                    )
                    error_item_ids.append(item_id)
                    continue

                # 3. Ghi file nội dung clean ra thư mục local TRƯỚC
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(clean_html)
                logger.info(f"💾 Đã lưu file clean tại: {file_path}")

                # 4. Tính toán MD5 của file clean vừa lưu
                local_clean_md5 = calculate_file_md5(file_path)

                if not local_clean_md5:
                    error_item_ids.append(item_id)
                    continue

                # 5. Kiểm tra xem đã có bản clean trên Drive chưa (từ bảng document_content)
                old_clean_drive_id = get_existing_drive_id_from_db(
                    conn, "document_content", item_id, "drive_id"
                )

                if old_clean_drive_id:
                    drive_clean_md5 = get_drive_file_md5(
                        drive_service, old_clean_drive_id
                    )

                    # THÀNH CÔNG 1: Nội dung clean không thay đổi
                    if drive_clean_md5 == local_clean_md5:
                        logger.info(
                            f"⏭️ Bỏ qua {item_id} vì nội dung clean không đổi trên Drive."
                        )
                        success_item_ids.append(item_id)
                        continue

                # 6. Upload file clean lên thư mục Drive MỚI
                new_clean_drive_id = upload_to_drive(
                    drive_service, file_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                # LỖI: Upload file clean thất bại
                if not new_clean_drive_id:
                    logger.error(f"❌ Upload file clean thất bại cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # THÀNH CÔNG 2: Upload file clean mới thành công -> Yield (Bỏ trường file_hash)
                logger.success(
                    f"✅ Đã upload file clean {item_id} (Drive ID: {new_clean_drive_id})"
                )
                success_item_ids.append(item_id)

                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "drive_id": new_clean_drive_id,
                }

            except Exception as e:
                logger.error(f"💥 Thất bại tại item {item_id}: {e}")
                error_item_ids.append(item_id)

    except Exception as e:
        logger.error(f"Lỗi khi truy vấn DB: {e}")
    finally:
        if conn:
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

    info = pipeline.run(document_content_resource(success_item_ids, error_item_ids))
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
        logger.warning(f"Có {len(error_item_ids)} items gặp lỗi và cần thu thập lại.")
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
