import dlt

from output_document_total import PATH_FILE_OUTPUT
from utils.config_by_path import ConfigByPath
from utils.jsonl_helper import yield_jsonl_records

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
    pipeline.run(document_total_resource())
    # logger.info(f"Kết quả pipeline: {info}")


if __name__ == "__main__":
    main()
