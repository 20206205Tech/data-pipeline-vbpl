from datetime import datetime

import dlt
import psycopg2
from loguru import logger

import env

# Đã bỏ import vectorstore vì nhảy từ bước 5 lên 10 chưa liên quan tới Pinecone
from utils.workflow_helper import document_state_resource


def main():
    conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

    # Đang ở bước 5
    current_step_id = 5
    # Nhảy thẳng lên bước 10
    final_step_id = 10

    try:
        # 1. Truy vấn TẤT CẢ các văn bản đang ở bước 5
        logger.info(
            f"Đang tìm kiếm tất cả các văn bản ở bước {current_step_id} cần fast-forward..."
        )
        with conn.cursor() as cur:
            # Lấy tất cả item_id có workflow_id = 5 (Đã bỏ filter status và LIMIT)
            query = """
                SELECT ds.item_id
                FROM "public"."document_state" ds
                WHERE ds.workflow_id = %s
            """
            cur.execute(query, (current_step_id,))
            rows = cur.fetchall()
            item_ids = [row[0] for row in rows]

        if not item_ids:
            logger.info(f"🎉 Không có văn bản nào đang kẹt ở bước {current_step_id}.")
            return

        logger.info(f"🔍 Tìm thấy {len(item_ids)} văn bản. Đang tiến hành xử lý...")

        # (Đã lược bỏ bước 2 xóa Vector trên Pinecone vì dữ liệu bước 5 chưa được embedding)

        # 3. Cập nhật state nhảy cóc lên bước 10 thông qua DLT
        logger.info(f"⏩ Đang cập nhật workflow_id lên {final_step_id}...")
        pipeline = dlt.pipeline(
            destination="postgres",
            dataset_name="public",
            pipeline_name="temp_fast_forward_step_5_to_10",
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
            f"✅ Đã nâng cấp thành công {len(item_ids)} văn bản lên bước {final_step_id}!"
        )

    except Exception as e:
        logger.error(f"❌ Xảy ra lỗi trong quá trình thực thi: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
