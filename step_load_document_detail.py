import os
from datetime import datetime

import dlt
import psycopg2
from loguru import logger

import env
from output_document_detail import PATH_FILE_OUTPUT, PATH_FOLDER_OUTPUT
from utils.config_by_path import ConfigByPath
from utils.google_drive import get_drive_service, upload_to_drive
from utils.hash_helper import calculate_file_hash, get_existing_hash_from_db
from utils.jsonl_helper import yield_jsonl_records
from utils.workflow_helper import log_workflow_state

config_by_path = ConfigByPath(__file__)


@dlt.resource(
    name="document_detail",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_detail_resource(item_ids):
    try:
        drive_service = get_drive_service()

        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

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
                continue

            item_ids.append(item_id)

            new_file_hash = calculate_file_hash(html_path)

            file_hash, drive_id = get_existing_hash_from_db(
                conn, "document_detail", item_id, "file_hash", "drive_id"
            )

            # Nếu file có thay đổi
            if file_hash != new_file_hash:
                new_drive_id = upload_to_drive(
                    drive_service, html_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID
                )

                # Nếu upload thất bại, ngắt hàm ngay lập tức (không yield gì cả)
                if not new_drive_id:
                    return

                # Nếu thành công, cập nhật lại biến để chuẩn bị yield
                drive_id = new_drive_id
                file_hash = new_file_hash

            # Lệnh yield này chỉ chạy khi: File KHÔNG đổi, HOẶC File CÓ đổi và ĐÃ upload thành công
            yield {
                "item_id": item_id,
                "update_at": datetime.now().isoformat(),
                "drive_id": drive_id,
                "file_hash": file_hash,
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

    item_ids = []

    info = pipeline.run(document_detail_resource(item_ids))
    logger.info(f"Kết quả pipeline: {info}")

    if item_ids:
        now = datetime.now()
        log_workflow_state(
            pipeline=pipeline, item_ids=item_ids, start_time=now, end_time=now
        )


if __name__ == "__main__":
    main()
