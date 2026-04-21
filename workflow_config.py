import hashlib
import json
import os
from dataclasses import asdict, dataclass, is_dataclass  # Thêm is_dataclass
from typing import Optional

from loguru import logger

import env


@dataclass
class WorkflowStep:
    id: int
    code: str
    description: str
    parent_id: Optional[int] = None


STEP_SETUP_WORKFLOW = WorkflowStep(
    id=1, code="step_setup_workflow", description="Khởi tạo workflow", parent_id=None
)
STEP_CRAWL_DOCUMENT_TOTAL = WorkflowStep(
    id=2,
    code="step_crawl_document_total",
    description="Cào thông tin tổng số lượng văn bản pháp luật hiện có trên hệ thống web.",
    parent_id=1,
)
STEP_LOAD_DOCUMENT_TOTAL = WorkflowStep(
    id=3,
    code="step_load_document_total",
    description="Tải và cập nhật tổng số lượng văn bản vừa thu thập vào database",
    parent_id=2,
)
STEP_CRAWL_DOCUMENT_LIST = WorkflowStep(
    id=4,
    code="step_crawl_document_list",
    description="Cào danh sách các văn bản pháp luật dựa trên sự thay đổi của tổng số lượng",
    parent_id=3,
)
STEP_LOAD_DOCUMENT_LIST = WorkflowStep(
    id=5,
    code="step_load_document_list",
    description="Lưu danh sách ID văn bản mới thu thập vào database để chuẩn bị cho các luồng tải chi tiết",
    parent_id=4,
)
STEP_CRAWL_DOCUMENT_DETAIL = WorkflowStep(
    id=6,
    code="step_crawl_document_detail",
    description="Cào toàn bộ mã nguồn HTML nội dung chi tiết của từng ID văn bản",
    parent_id=5,
)
STEP_LOAD_DOCUMENT_DETAIL = WorkflowStep(
    id=7,
    code="step_load_document_detail",
    description="Upload file HTML chi tiết lên Google Drive",
    parent_id=6,
)


STEP_EXTRACT_DOCUMENT_INFO = WorkflowStep(
    id=8,
    code="step_extract_document_info",
    description="Bóc tách siêu dữ liệu (số hiệu, cơ quan ban hành, ngày hiệu lực, người ký...) từ HTML.",
    parent_id=7,
)
STEP_EXTRACT_DOCUMENT_CONTENT = WorkflowStep(
    id=9,
    code="step_extract_document_content",
    description="Trích xuất và làm sạch phần nội dung văn bản chính từ HTML",
    parent_id=8,
)
STEP_EXTRACT_DOCUMENT_MARKDOWN = WorkflowStep(
    id=10,
    code="step_extract_document_markdown",
    description="Chuyển đổi nội dung HTML sạch sang định dạng Markdown",
    parent_id=9,
)

STEP_RAG_SUMMARY = WorkflowStep(
    id=11,
    code="step_rag_summary",
    description="Tạo tóm tắt nội dung văn bản từ markdown",
    parent_id=10,
)
STEP_RAG_CHUNKING = WorkflowStep(
    id=12,
    code="step_rag_chunking",
    description="Cắt nhỏ nội dung Markdown bằng LLM",
    parent_id=11,
)
STEP_RAG_CONTEXT = WorkflowStep(
    id=13,
    code="step_rag_context",
    description="Tạo ngữ cảnh cho từng đoạn văn bản",
    parent_id=12,
)
# STEP_CALL_COLAB = WorkflowStep(
#     id=14,
#     code="step_call_colab",
#     description="Tạo vector embedding cho từng đoạn văn bản",
#     parent_id=13,
# )
STEP_RAG_EMBEDDING = WorkflowStep(
    id=14,
    code="step_rag_embedding",
    description="Tạo vector embedding cho từng đoạn văn bản",
    parent_id=13,
)
# STEP_CLEAN_DOCUMENT_PENDING = WorkflowStep(
#     id=15,
#     code="step_clean_document_pending",
#     description="Tạo vector embedding cho từng đoạn văn bản",
#     parent_id=14,
# )


def generate_workflow_version(steps: list[WorkflowStep]) -> str:
    if not steps:
        return "1.0.0"

    steps_dict = [asdict(step) for step in steps]
    steps_dict_sorted = sorted(steps_dict, key=lambda x: x["id"])

    json_str = json.dumps(steps_dict_sorted, sort_keys=True)

    full_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    return full_hash[:12]


def workflow_to_mermaid(data):
    dict_data = [asdict(item) if is_dataclass(item) else item for item in data]

    mermaid_lines = ["```mermaid", "flowchart TD"]
    style_lines = ["\n    %% Định nghĩa kiểu dáng cho node không hoạt động"]

    for item in dict_data:
        node_id = item["id"]
        code = item["code"]
        # desc = item["description"].replace("Chạy lệnh ", "")
        mermaid_lines.append(f'    N{node_id}["[{node_id}] {code}"]')

        # if not item.get("is_active"):
        #     style_lines.append(
        #         f"    style N{node_id} fill:#e3f2fd,stroke:#2196f3,stroke-width:2px"
        #     )

    if len(style_lines) > 1:
        mermaid_lines.extend(style_lines)

    mermaid_lines.append("\n    %% Các liên kết")

    for item in dict_data:
        if item.get("parent_id") is not None:
            child_id = item["id"]
            parent_id = item["parent_id"]
            mermaid_lines.append(f"    N{parent_id} --> N{child_id}")

    mermaid_lines.append("```")

    # Cấu trúc nội dung file Markdown
    mermaid_content = "\n".join(mermaid_lines)
    markdown_content = "# Sơ đồ\n\n" f"{mermaid_content}\n"

    # Ghi nội dung vào file
    try:
        output_file = os.path.join(env.PATH_FOLDER_DOCS, "workflow.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Đã ghi thành công sơ đồ Mermaid vào file {output_file}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file {output_file}: {e}")


def workflow_to_json(data):
    # 1. Chuyển đổi dữ liệu
    dict_data = [asdict(item) if is_dataclass(item) else item for item in data]

    # 2. Xây dựng dictionary steps_config (chứa các bước workflow)
    steps_config = {}
    for item in dict_data:
        code = item.get("code")
        if code:
            steps_config[code] = True

    # 3. Gói steps_config vào trong client_payload và thêm event_type
    final_payload = {
        "event_type": "data_pipeline_trigger",
        "client_payload": {"steps_config": steps_config},
    }

    # 4. Xác định đường dẫn file đầu ra
    output_file = os.path.join(env.PATH_FOLDER_DOCS, "workflow.json")

    # 5. Ghi nội dung ra file JSON
    try:
        # Sử dụng indent=4 để format file JSON đẹp và dễ nhìn hơn
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=4)

        logger.info(f"Đã ghi thành công dữ liệu JSON vào file {output_file}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file {output_file}: {e}")


def workflow_to_github_action(data):
    # 1. Chuyển đổi dữ liệu
    dict_data = [asdict(item) if is_dataclass(item) else item for item in data]

    # 2. Phần đầu cố định của GitHub Action
    yaml_content = """name: data_pipeline_trigger

on:
  workflow_dispatch:
  repository_dispatch:
    types: [data_pipeline_trigger]

jobs:
  data_pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install Doppler CLI
        uses: dopplerhq/cli-action@v1

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version-file: ".python-version"

      - name: Install dependencies
        run: uv sync

      - name: Cache Scrapy HTTP Cache
        uses: actions/cache@v4
        with:
          path: .scrapy
          key: ${{ runner.os }}-scrapy-cache-${{ github.workflow }}
          restore-keys: |
            ${{ runner.os }}-scrapy-cache-
"""

    # 3. Phần sau động sinh ra dựa trên "code" của từng step
    for item in dict_data:
        code = item.get("code")
        if code:
            step_block = f"""
      - name: {code}
        if: ${{{{ github.event_name == 'workflow_dispatch' || github.event.client_payload.steps_config.{code} == true }}}}
        env:
          DOPPLER_TOKEN: ${{{{ secrets.DOPPLER_TOKEN }}}}
        run: |
          doppler run -p 20206205tech -c prod -- uv run python {code}.py
"""
            yaml_content += step_block

    # 4. Xác định đường dẫn file (Dùng os.path.join cho từng thư mục để an toàn trên mọi HĐH)
    output_dir = os.path.join(env.PATH_FOLDER_PROJECT, ".github", "workflows")
    output_file = os.path.join(output_dir, "data_pipeline.yml")

    # Tạo thư mục nếu chưa tồn tại (tránh lỗi FileNotFoundError)
    os.makedirs(output_dir, exist_ok=True)

    # 5. Ghi nội dung ra file YAML
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        logger.info(f"Đã ghi thành công file Github Action vào {output_file}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file {output_file}: {e}")


workflow_data = []

for key, value in list(globals().items()):
    if key.isupper() and isinstance(value, WorkflowStep) and key.startswith("STEP_"):
        workflow_data.append(value)

workflow_version = generate_workflow_version(workflow_data)
