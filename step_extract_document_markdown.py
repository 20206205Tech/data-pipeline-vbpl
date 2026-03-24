import os
from datetime import datetime

import dlt
import psycopg2
from loguru import logger
from markdownify import markdownify

import env
import workflow_config
from utils.config_by_path import ConfigByPath

# Mở comment và import đủ các hàm Drive, nhớ thêm get_drive_file_md5
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
    upload_to_drive,
)

# Đổi sang sử dụng hàm lấy drive_id và tính MD5
from utils.hash_helper import calculate_file_md5, get_existing_drive_id_from_db
from utils.workflow_helper import (
    document_state_resource,
    fetch_and_lock_pending_tasks,
    get_workflow_item_counts_via_pipeline,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def convert_html_to_markdown(html_content):
    """Chuyển đổi HTML sang Markdown với cấu hình chuẩn"""
    try:
        if not html_content:
            return None
        return markdownify(html_content, heading_style="ATX", strip=["script", "style"])
    except Exception as e:
        logger.error(f"Lỗi chuyển đổi Markdown: {e}")
        return None


@dlt.resource(
    name="document_markdown",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_markdown_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=None,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có dữ liệu Markdown mới cần xử lý.")
            return

        for item_id in pending_item_ids:
            file_name = f"{item_id}.md"
            file_path = os.path.join(PATH_FOLDER_OUTPUT, file_name)

            try:
                # 1. Lấy drive_id của nội dung html đã clean từ bảng document_content
                drive_content_file_id = get_existing_drive_id_from_db(
                    conn, "document_content", item_id, "drive_id"
                )

                if not drive_content_file_id:
                    logger.warning(
                        f"Không tìm thấy drive_id nội dung html clean cho {item_id}"
                    )
                    error_item_ids.append(item_id)
                    continue

                logger.info(f"Đang xử lý Markdown cho item: {item_id}")

                # 2. Tải HTML clean về và convert sang Markdown
                html_bytes = download_from_drive(drive_service, drive_content_file_id)
                html_text = html_bytes.decode("utf-8")

                md_content = convert_html_to_markdown(html_text)

                if not md_content:
                    logger.warning(f"⚠️ Không thể tạo markdown content cho {item_id}")
                    error_item_ids.append(item_id)
                    continue

                # 3. TIẾN HÀNH: Ghi file local TRƯỚC để tính MD5
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                logger.info(f"💾 Đã lưu file local: {file_path}")

                # 4. Tính MD5 của file Markdown vừa lưu
                local_md5 = calculate_file_md5(file_path)

                if not local_md5:
                    error_item_ids.append(item_id)
                    continue

                # 5. Kiểm tra xem đã có bản Markdown trên Drive chưa (từ bảng document_markdown)
                old_markdown_drive_id = get_existing_drive_id_from_db(
                    conn, "document_markdown", item_id, "drive_id"
                )

                if old_markdown_drive_id:
                    # Gọi API lấy MD5 của file trên Drive về
                    drive_md5 = get_drive_file_md5(drive_service, old_markdown_drive_id)

                    # THÀNH CÔNG 1: Markdown không thay đổi -> Bỏ qua
                    if drive_md5 == local_md5:
                        logger.info(
                            f"⏭️ Bỏ qua {item_id} vì nội dung Markdown không đổi trên Drive."
                        )
                        success_item_ids.append(item_id)
                        continue

                # 6. Upload file Markdown lên Google Drive
                new_drive_id = upload_to_drive(
                    drive_service, file_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                if not new_drive_id:
                    logger.error(f"❌ Upload thất bại Markdown cho {item_id}")
                    error_item_ids.append(item_id)  # Ghi nhận lỗi
                    continue

                # 7. THÀNH CÔNG 2: Upload mới thành công -> Yield (Bỏ trường file_hash)
                logger.success(
                    f"✅ Đã upload Markdown cho {item_id} (Drive ID: {new_drive_id})"
                )
                success_item_ids.append(item_id)

                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "drive_id": new_drive_id,
                }

            except Exception as e:
                logger.error(f"💥 Thất bại tại item {item_id}: {e}")
                error_item_ids.append(item_id)  # Ghi nhận lỗi có Exception

    except psycopg2.errors.UndefinedTable as e:
        logger.warning(f"Bảng chưa tồn tại hoặc lỗi SQL: {e}")
        if conn:
            conn.rollback()
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

    info = pipeline.run(document_markdown_resource(success_item_ids, error_item_ids))
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
        logger.error(f"Có {len(error_item_ids)} items gặp lỗi và cần thu thập lại.")
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
