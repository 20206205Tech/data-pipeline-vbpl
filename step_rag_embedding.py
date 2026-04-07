import os
import shutil
from datetime import datetime

import dlt
import psycopg2
from langchain_core.documents import Document
from loguru import logger

import env
from rag.vectorstore import pinecone_index, vectorstore
from utils.config_by_path import ConfigByPath
from utils.document_helper import is_document_invalid
from utils.google_drive import (
    download_from_drive,
    get_drive_file_md5,
    get_drive_service,
)
from utils.hash_helper import (
    get_existing_drive_ids_from_db,
    get_existing_hashes_from_db,
)
from utils.workflow_helper import (
    fetch_and_lock_pending_tasks,
    log_error_workflow_state,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)
PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


@dlt.resource(
    name="document_embedding",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_embedding_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có tài liệu nào cần xử lý embedding.")
            return

        logger.info(
            f"Đang fetch toàn bộ metadata và history hàng loạt cho {len(pending_item_ids)} items..."
        )

        dict_all_info = {}
        str_item_ids = tuple(str(id) for id in pending_item_ids)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT item_id, status, effective_date, issuing_agency, document_number, issue_date, title, signer, position
                    FROM "public"."document_info"
                    WHERE item_id IN %s
                    """,
                    (str_item_ids,),
                )
                columns = [desc[0] for desc in cur.description]
                for row in cur.fetchall():
                    dict_all_info[str(row[0])] = dict(zip(columns, row))
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
        except Exception as e:
            logger.error(f"Lỗi khi fetch document_info: {e}")
            conn.rollback()

        dict_context_drive_ids = get_existing_drive_ids_from_db(
            conn, "document_context", pending_item_ids, "drive_id"
        )

        dict_embedding_hashes = get_existing_hashes_from_db(
            conn, "document_embedding", pending_item_ids, "context_md5", "status"
        )

        for item_id in pending_item_ids:
            item_workspace = os.path.join(
                PATH_FOLDER_OUTPUT, f"embed_workspace_{item_id}"
            )

            try:
                info_record = dict_all_info.get(str(item_id), {})
                raw_status = info_record.get("status")

                safe_status = (
                    raw_status.strip()
                    if raw_status and raw_status.strip()
                    else "Chưa xác định"
                )

                if is_document_invalid(raw_status):
                    logger.info(
                        f"🗑️ Tài liệu {item_id} có trạng thái '{raw_status}'. Đang tiến hành xóa khỏi Vector DB..."
                    )

                    try:
                        pinecone_index.delete(filter={"item_id": {"$eq": str(item_id)}})
                        logger.success(
                            f"✅ Đã xóa vector cũ của {item_id} trên vectorDB."
                        )
                    except Exception as delete_err:
                        logger.error(
                            f"❌ Lỗi khi xóa vector của {item_id} trên vectorDB: {delete_err}"
                        )
                        error_item_ids.append(item_id)
                        continue

                    success_item_ids.append(item_id)
                    yield {
                        "item_id": item_id,
                        "update_at": datetime.now().isoformat(),
                        "context_md5": None,
                        "vector_count": 0,
                        "status": "deleted",
                    }
                    continue  # Xóa xong thì continue để không nhúng (embed) lại văn bản này nữa

                context_drive_id = dict_context_drive_ids.get(str(item_id))

                if not context_drive_id:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Không tìm thấy file ZIP Context (không có drive_id)."
                    )
                    error_item_ids.append(item_id)
                    continue

                current_context_md5 = get_drive_file_md5(
                    drive_service, context_drive_id
                )

                if not current_context_md5:
                    logger.warning(
                        f"⚠️ Bỏ qua {item_id}: Không lấy được MD5 từ Google Drive."
                    )
                    error_item_ids.append(item_id)
                    continue

                old_context_md5, _ = dict_embedding_hashes.get(
                    str(item_id), (None, None)
                )

                if old_context_md5 == current_context_md5:
                    logger.info(
                        f"⏭️ Bỏ qua {item_id}: Nội dung chunks không thay đổi, vector đã up-to-date."
                    )
                    success_item_ids.append(item_id)
                    continue

                logger.info(
                    f"📥 Đang tải và giải nén Chunks (Context) cho tài liệu: {item_id}"
                )

                extract_dir = os.path.join(item_workspace, "chunks")
                os.makedirs(extract_dir, exist_ok=True)

                zip_bytes = download_from_drive(drive_service, context_drive_id)
                zip_path = os.path.join(item_workspace, "temp.zip")
                with open(zip_path, "wb") as f:
                    f.write(zip_bytes)

                shutil.unpack_archive(zip_path, extract_dir)

                chunk_files = [f for f in os.listdir(extract_dir) if f.endswith(".md")]
                logger.info(
                    f"🧠 Đang tạo vector và lưu vào database cho {len(chunk_files)} chunks..."
                )

                documents = []
                doc_ids = []

                base_metadata = {
                    "item_id": str(item_id),
                    "legal_status": safe_status,
                }

                keys_to_add = [
                    "title",
                    "document_number",
                    "issuing_agency",
                    "issue_date",
                    "effective_date",
                    "signer",
                    "position",
                ]

                for key in keys_to_add:
                    val = info_record.get(key)
                    if val:
                        base_metadata[key] = str(val).strip()

                for chunk_filename in chunk_files:
                    with open(
                        os.path.join(extract_dir, chunk_filename), "r", encoding="utf-8"
                    ) as f:
                        text = f.read().strip()
                    if not text:
                        continue

                    chunk_metadata = base_metadata.copy()
                    chunk_metadata["source"] = chunk_filename

                    # ID đồng bộ để ghi đè (upsert) tránh trùng lặp trong vector DB
                    doc_id = f"{item_id}_{chunk_filename.replace('.md', '')}"

                    documents.append(
                        Document(
                            page_content=text,
                            metadata=chunk_metadata,
                        )
                    )
                    doc_ids.append(doc_id)

                if documents:
                    vectorstore.add_documents(documents=documents, ids=doc_ids)
                    logger.success(
                        f"✅ Đã lưu {len(documents)} vectors vào Vector DB cho: {item_id}"
                    )

                success_item_ids.append(item_id)
                yield {
                    "item_id": item_id,
                    "update_at": datetime.now().isoformat(),
                    "context_md5": current_context_md5,
                    "vector_count": len(documents),
                    "status": "embedded",
                }

            except Exception as e:
                logger.error(f"💥 Lỗi tại item {item_id}: {e}")
                error_item_ids.append(item_id)

            finally:
                if os.path.exists(item_workspace):
                    shutil.rmtree(item_workspace, ignore_errors=True)

    except Exception as e:
        logger.error(f"Lỗi hệ thống Database/Drive: {e}")
    finally:
        if "conn" in locals() and conn:
            conn.close()


def main():
    pipeline = dlt.pipeline(
        destination="postgres",
        dataset_name="public",
        pipeline_name=config_by_path.NAME,
    )

    success_item_ids = []
    error_item_ids = []
    start_time = datetime.now()

    pipeline.run(document_embedding_resource(success_item_ids, error_item_ids))
    # logger.info(f"Kết quả pipeline: {info}")

    if success_item_ids:
        log_workflow_state(
            pipeline=pipeline,
            item_ids=success_item_ids,
            start_time=start_time,
            end_time=datetime.now(),
        )
        logger.info(f"Đã xử lý thành công {len(success_item_ids)} items.")

    if error_item_ids:
        logger.error(
            f"Có {len(error_item_ids)} items gặp lỗi và cần thu thập/chạy lại."
        )
        logger.warning(f"Danh sách lỗi: {error_item_ids}")

        log_error_workflow_state(pipeline, error_item_ids, start_time)


if __name__ == "__main__":
    if not env.CRAWL_DATA_ENV_DEV:
        main()
    else:
        logger.error("🚧 Chạy ở chế độ DEV")
