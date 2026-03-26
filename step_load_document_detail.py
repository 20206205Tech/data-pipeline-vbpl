import os
from datetime import datetime

import dlt
import psycopg2
from loguru import logger

import env
from output_document_detail import PATH_FILE_OUTPUT, PATH_FOLDER_OUTPUT
from utils.config_by_path import ConfigByPath
from utils.google_drive import get_drive_file_md5, get_drive_service, upload_to_drive
from utils.hash_helper import calculate_file_md5, get_existing_drive_id_from_db
from utils.jsonl_helper import yield_jsonl_records
from utils.workflow_helper import (
    document_state_resource,
    get_workflow_item_counts_via_pipeline,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)


@dlt.resource(
    name="document_detail",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_detail_resource(success_item_ids, error_item_ids):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        with open(PATH_FILE_OUTPUT, "r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)

        logger.info(f"Tổng số dòng cần xử lý: {total_lines}")

        for record in yield_jsonl_records(PATH_FILE_OUTPUT):
            item_id = record.get("item_id")

            if not item_id:
                logger.warning(f"Không tìm thấy item_id trong record: {record}")
                continue

            html_path = os.path.join(PATH_FOLDER_OUTPUT, f"{item_id}.html")

            if not os.path.exists(html_path):
                logger.warning(
                    f"File HTML không tồn tại item_id {item_id}: {html_path}"
                )
                error_item_ids.append(item_id)
                continue

            # 1. Tính MD5 của file dưới máy
            local_md5 = calculate_file_md5(html_path)
            if not local_md5:
                error_item_ids.append(item_id)
                continue

            # 2. Lấy drive_id cũ từ DB
            drive_id = get_existing_drive_id_from_db(
                conn, "document_detail", item_id, "drive_id"
            )

            # 3. Nếu DB đã có drive_id, gọi API Drive để lấy MD5 về so sánh
            if drive_id:
                drive_md5 = get_drive_file_md5(drive_service, drive_id)

                if drive_md5 == local_md5:
                    logger.info(f"File không đổi trên Drive, bỏ qua item_id: {item_id}")
                    success_item_ids.append(item_id)
                    continue

            # 4. Nếu chưa có drive_id HOẶC hash khác nhau -> Upload lại
            new_drive_id = upload_to_drive(
                drive_service, html_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
            )

            if not new_drive_id:
                logger.error(f"Upload thất bại, cần thu thập lại item_id: {item_id}")
                error_item_ids.append(item_id)
                continue

            success_item_ids.append(item_id)

            # 5. Trả về DLT: Xoá trường file_hash, chỉ lưu drive_id
            yield {
                "item_id": item_id,
                "update_at": datetime.now().isoformat(),
                "drive_id": new_drive_id,
            }
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

    info = pipeline.run(document_detail_resource(success_item_ids, error_item_ids))
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
                workflow_id=0,
                item_ids=error_item_ids,
                start_time=start_time,
                end_time=datetime.now(),
            )
        )

    get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
