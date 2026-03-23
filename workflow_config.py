from dataclasses import dataclass
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


# STEP_WORKFLOW    = WorkflowStep(1, "step_workflow", "Khởi tạo workflow trong database và sinh sơ đồ luồng Mermaid.")
# CRAWL_TOTAL      = WorkflowStep(2, "step_crawl_document_total", "Cào thông tin tổng số lượng văn bản pháp luật hiện có trên hệ thống web.", parent_id=1)
# LOAD_TOTAL       = WorkflowStep(3, "step_load_document_total", "Tải và cập nhật tổng số lượng văn bản vừa thu thập vào cơ sở dữ liệu PostgreSQL.", parent_id=2)
# CRAWL_LIST       = WorkflowStep(4, "step_crawl_document_list", "Cào danh sách các ID/URL văn bản pháp luật dựa trên sự thay đổi của tổng số lượng.", parent_id=3)
# LOAD_LIST        = WorkflowStep(5, "step_load_document_list", "Lưu danh sách ID văn bản mới thu thập vào database để chuẩn bị cho các luồng tải chi tiết.", parent_id=4)
# CRAWL_DETAIL     = WorkflowStep(6, "step_crawl_document_detail", "Cào toàn bộ mã nguồn HTML nội dung chi tiết của từng ID văn bản.", parent_id=5)
# LOAD_DETAIL      = WorkflowStep(7, "step_load_document_detail", "Upload file HTML chi tiết lên Google Drive và lưu metadata (drive_id, file_hash) vào database.", parent_id=6)
# EXTRACT_INFO     = WorkflowStep(8, "step_extract_document_info", "Bóc tách siêu dữ liệu (số hiệu, cơ quan ban hành, ngày hiệu lực, người ký...) từ HTML.", parent_id=7)
# EXTRACT_CONTENT  = WorkflowStep(9, "step_extract_document_content", "Trích xuất và làm sạch phần nội dung văn bản chính từ HTML, sau đó upload bản sạch lên Drive.", parent_id=8)
# EXTRACT_MARKDOWN = WorkflowStep(10, "step_extract_document_markdown", "Chuyển đổi nội dung HTML sạch sang định dạng Markdown chuẩn và lưu trữ lên Drive.", parent_id=9)
# RAG_SUMMARY      = WorkflowStep(11, "step_rag_summary", "Tạo tóm tắt nội dung văn bản từ markdown.", parent_id=10)
# RAG_CHUNKING     = WorkflowStep(12, "step_rag_chunking", "Cắt nhỏ nội dung Markdown bằng LLM.", parent_id=11)
# RAG_CONTEXT      = WorkflowStep(13, "step_rag_context", "Tạo ngữ cảnh cho từng đoạn văn bản từ markdown.", parent_id=12)


workflow_data = []

for key, value in list(globals().items()):
    if key.isupper() and isinstance(value, WorkflowStep):
        workflow_data.append(value)
        # logger.info(f"{key}: value={value}")
logger.info(f"{workflow_data}")
