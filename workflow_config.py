import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Optional

from loguru import logger


@dataclass
class WorkflowStep:
    id: int
    code: str
    description: str
    parent_id: Optional[int] = None


STEP_MOT = WorkflowStep(id=1, code="MOT", description="MOT")
STEP_HAI = WorkflowStep(id=2, code="HAI", description="HAI", parent_id=1)

workflow_data = []

for key, value in list(globals().items()):
    if key.isupper() and isinstance(value, WorkflowStep):
        workflow_data.append(value)


def generate_workflow_version(steps: list[WorkflowStep]) -> str:
    if not steps:
        return "1.0.0"

    steps_dict = [asdict(step) for step in steps]
    steps_dict_sorted = sorted(steps_dict, key=lambda x: x["id"])

    json_str = json.dumps(steps_dict_sorted, sort_keys=True)

    full_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    return full_hash[:12]


workflow_version = generate_workflow_version(workflow_data)

logger.info(f"Workflow Data: {workflow_data}")
logger.success(f"Generated Workflow Version: {workflow_version}")
