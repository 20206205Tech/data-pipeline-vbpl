<!--  -->

cd ~/Desktop/20206205/dev-docker-compose/docker/postgres
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml up -d

<!--  -->

cd ~/Desktop/20206205/data-pipeline-vbpl
doppler setup --project 20206205tech --config dev
doppler run -- python step_setup_workflow.py

<!--  -->

<!-- doppler run -- python step_crawl_document_total.py -->

doppler run -- python step_load_document_total.py

<!-- doppler run -- python step_crawl_document_list.py -->

doppler run -- python step_load_document_list.py

<!-- doppler run -- python step_crawl_document_detail.py -->

doppler run -- python step_load_document_detail.py

doppler run -- python step_extract_document_info.py
doppler run -- python step_extract_document_content.py
doppler run -- python step_extract_document_markdown.py

<!--  -->

doppler run -- python step_rag_summary.py
doppler run -- python step_rag_chunking.py
doppler run -- python step_rag_context.py

<!-- doppler run -- python step_call_colab.py -->

doppler run -- python step_rag_embedding.py

<!-- doppler run -- python step_clean_document_pending.py -->
