import dlt
from loguru import logger

from output_document_total import PATH_FILE_OUTPUT
from utils.config_by_path import ConfigByPath
from utils.jsonl_helper import yield_jsonl_records
from utils.workflow_helper import get_workflow_item_counts_via_pipeline

config_by_path = ConfigByPath(__file__)


@dlt.resource(name="document_total", write_disposition="append")
def document_total_resource():
    yield from yield_jsonl_records(PATH_FILE_OUTPUT)


def main():
    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )
    info = pipeline.run(document_total_resource())
    logger.info(f"Kết quả pipeline: {info}")

    get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
