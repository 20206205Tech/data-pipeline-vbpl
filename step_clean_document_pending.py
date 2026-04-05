from datetime import datetime
from typing import List

import dlt
from loguru import logger

from utils.config_by_path import ConfigByPath
from utils.workflow_helper import get_workflow_item_count, log_error_workflow_state

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


def get_stale_document_ids(pipeline: dlt.Pipeline) -> List[int]:
    """
    Truy vấn các item_id có start_time nhưng chưa có end_time và đã trôi qua 12 tiếng.
    """
    query = """
        SELECT item_id
        FROM document_state
        WHERE start_time IS NOT NULL
          AND end_time IS NULL
          AND start_time <= NOW() - INTERVAL '12 hours';
    """

    try:
        with pipeline.sql_client() as client:
            results = client.execute_sql(query)
            # Giả định kết quả trả về là list of tuples: [(id1,), (id2,)]
            return [row[0] for row in results] if results else []
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn cơ sở dữ liệu: {e}")
        return []


def main():
    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )

    # 1. Lấy danh sách các ID bị lỗi/treo
    error_item_ids = get_stale_document_ids(pipeline)

    # 2. Xử lý và cập nhật trạng thái nếu tìm thấy document bị treo
    if error_item_ids:
        logger.info(
            f"Tìm thấy {len(error_item_ids)} documents bị treo. Đang cập nhật trạng thái..."
        )

        # Lưu lại start_time của tiến trình cập nhật này
        start_time = datetime.now()

        log_error_workflow_state(pipeline, error_item_ids, start_time)
    else:
        logger.info("Không có document nào bị treo.")

    get_workflow_item_count(pipeline)


if __name__ == "__main__":
    main()
