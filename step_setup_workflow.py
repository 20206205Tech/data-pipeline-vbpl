import dataclasses

import dlt

import workflow_config
from utils.config_by_path import ConfigByPath

config_by_path = ConfigByPath(__file__)


@dlt.resource(name="workflows", write_disposition="replace")
def workflow_resource():
    for item in workflow_config.workflow_data:
        item_dict = dataclasses.asdict(item)
        item_dict["workflow_version"] = workflow_config.workflow_version
        yield item_dict


def main():
    workflow_config.workflow_to_mermaid(workflow_config.workflow_data)
    workflow_config.workflow_to_json(workflow_config.workflow_data)
    workflow_config.workflow_to_github_action(workflow_config.workflow_data)

    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )

    pipeline.run(workflow_resource())
    # logger.info(f"Kết quả pipeline: {info}")


if __name__ == "__main__":
    main()
