import time
from datetime import datetime

import dlt
import psycopg2
from loguru import logger

import env
import workflow_config
from rag.vectorstore import pinecone_index
from utils.document_helper import STATUS_TO_SKIP
from utils.workflow_helper import document_state_resource


def main():
    conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

    # Đang ở bước Markdown (10)
    current_step_id = workflow_config.STEP_EXTRACT_DOCUMENT_MARKDOWN.id
    # Nhảy thẳng lên bước cuối (14)
    final_step_id = workflow_config.STEP_RAG_EMBEDDING.id

    try:
        # 1. Truy vấn các văn bản hết hiệu lực đang kẹt ở bước 10
        logger.info("Đang tìm kiếm các văn bản hết hiệu lực cần fast-forward...")
        with conn.cursor() as cur:
            query = """
                SELECT ds.item_id
                FROM "public"."document_state" ds
                JOIN "public"."document_info" di ON ds.item_id = di.item_id
                WHERE ds.workflow_id = %s
                  AND di.status IN %s
                LIMIT 200
            """
            cur.execute(query, (current_step_id, tuple(STATUS_TO_SKIP)))
            rows = cur.fetchall()
            item_ids = [row[0] for row in rows]

        if not item_ids:
            logger.info("🎉 Không có văn bản hết hiệu lực nào đang kẹt ở bước Markdown.")
            return

        logger.info(f"🔍 Tìm thấy {len(item_ids)} văn bản. Đang tiến hành xử lý...")

        # 2. Xóa Vector trên Pinecone (Tránh Ghost Data)
        logger.info("🧹 Đang dọn dẹp dữ liệu cũ trên VectorDB (Pinecone)...")
        for item_id in item_ids:
            try:
                # Xóa toàn bộ chunk vector của item_id này (giống logic trong step_rag_embedding)
                pinecone_index.delete(filter={"item_id": {"$eq": str(item_id)}})

                # Pinecone giới hạn 5 req/sec (delete by metadata).
                # Nghỉ 0.25s để duy trì tốc độ 4 req/sec, tránh dính lỗi "Too Many Requests"
                time.sleep(0.25)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa vector của {item_id} trên Pinecone: {e}")

        logger.success("Đã dọn dẹp xong VectorDB.")

        # 3. Cập nhật state nhảy cóc lên bước cuối thông qua DLT
        logger.info(f"⏩ Đang cập nhật workflow_id lên {final_step_id}...")
        pipeline = dlt.pipeline(
            destination="postgres",
            dataset_name="public",
            pipeline_name="temp_fast_forward_invalid",
        )

        start_time = datetime.now()
        pipeline.run(
            document_state_resource(
                workflow_id=final_step_id,
                item_ids=item_ids,
                start_time=start_time,
                end_time=datetime.now(),
            )
        )
        logger.success(
            f"✅ Đã nâng cấp thành công {len(item_ids)} văn bản lên bước cuối cùng!"
        )

    except Exception as e:
        logger.error(f"❌ Xảy ra lỗi trong quá trình thực thi: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
