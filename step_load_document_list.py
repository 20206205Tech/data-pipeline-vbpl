from datetime import datetime

import dlt
from loguru import logger

from output_document_list import PATH_FILE_OUTPUT
from utils.config_by_path import ConfigByPath
from utils.jsonl_helper import yield_jsonl_records
from utils.workflow_helper import (
    get_workflow_item_counts_via_pipeline,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)


def main():
    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )

    records = list(yield_jsonl_records(PATH_FILE_OUTPUT))
    item_ids = [r.get("item_id") for r in records if r.get("item_id")]

    if not item_ids:
        logger.warning("Không có item_id nào được thu thập. Bỏ qua ghi log.")
        return

    if item_ids:
        now = datetime.now()
        log_workflow_state(
            pipeline=pipeline, item_ids=item_ids, start_time=now, end_time=now
        )

    get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
