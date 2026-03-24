# Sơ đồ

```mermaid
flowchart TD
    N1["[1] step_setup_workflow"]
    N2["[2] step_crawl_document_total"]
    N3["[3] step_load_document_total"]
    N4["[4] step_crawl_document_list"]
    N5["[5] step_load_document_list"]
    N6["[6] step_crawl_document_detail"]
    N7["[7] step_load_document_detail"]
    N8["[8] step_extract_document_info"]
    N9["[9] step_extract_document_content"]
    N10["[10] step_extract_document_markdown"]
    N11["[11] step_rag_summary"]
    N12["[12] step_rag_chunking"]
    N13["[13] step_rag_context"]
    N14["[14] step_rag_embedding"]
    N15["[15] step_clean_document_pending"]

    %% Các liên kết
    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 --> N6
    N6 --> N7
    N7 --> N8
    N8 --> N9
    N9 --> N10
    N10 --> N11
    N11 --> N12
    N12 --> N13
    N13 --> N14
    N14 --> N15
```
