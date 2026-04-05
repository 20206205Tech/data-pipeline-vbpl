from datetime import datetime
from typing import Any, List, Optional, Tuple

import dlt
import plotext as plt
from loguru import logger

import env
import workflow_config


def get_workflow_id(pipeline: dlt.Pipeline) -> int:
    workflow_code = pipeline.pipeline_name

    try:
        with pipeline.sql_client() as client:
            query = f"""
                SELECT id
                FROM "public"."workflows"
                WHERE code = '{workflow_code}'
                LIMIT 1
            """
            rows = client.execute_sql(query)

            if rows and len(rows) > 0:
                return rows[0][0]
            else:
                raise ValueError(
                    f"Không tìm thấy workflow có code là '{workflow_code}' trong database."
                )

    except Exception as e:
        logger.error(f"Lỗi khi lấy ID cho workflow '{workflow_code}': {e}")
        raise


@dlt.resource(
    name="document_state",
    write_disposition="merge",
    primary_key="item_id",
    columns={
        "workflow_id": {"data_type": "bigint"},
        "item_id": {"data_type": "bigint", "nullable": True},
        "start_time": {"data_type": "timestamp", "nullable": True},
        "end_time": {"data_type": "timestamp", "nullable": True},
        "workflow_version": {"data_type": "text", "nullable": True},
    },
)
def document_state_resource(
    workflow_id: int,
    item_ids: Optional[List[int]] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    current_version = workflow_config.workflow_version

    if item_ids:
        for item_id in item_ids:
            yield {
                "workflow_id": workflow_id,
                "item_id": item_id,
                "start_time": start_time,
                "end_time": end_time,
                "workflow_version": current_version,
            }
    else:
        yield {
            "workflow_id": workflow_id,
            "item_id": None,
            "start_time": start_time,
            "end_time": end_time,
            "workflow_version": current_version,
        }


def log_workflow_state(
    pipeline: dlt.Pipeline,
    item_ids: Optional[List[int]] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Any:
    try:
        workflow_id = get_workflow_id(pipeline)

        workflow_state_info = pipeline.run(
            document_state_resource(
                workflow_id=workflow_id,
                item_ids=item_ids,
                start_time=start_time,
                end_time=end_time,
            )
        )

        logger.info(
            f"Đã lưu trạng thái workflow_id={workflow_id}: item_ids={item_ids}, start={start_time}, end={end_time}"
        )

        return workflow_state_info

    except Exception as e:
        logger.exception(f"Lỗi khi lưu trạng thái: {e}")
        raise


def fetch_and_lock_pending_tasks(conn, step_code: str, limit: int = None) -> list:
    if limit is None:
        if env.CRAWL_DATA_ENV_DEV:
            limit = 2
        else:
            limit = 9999

    logger.info(f"Bắt đầu lấy và khóa task cho step_code='{step_code}', limit={limit}")

    limit_clause = "LIMIT %s" if limit is not None else ""
    params = [limit] if limit is not None else []

    query = f"""
    WITH step_info AS (
        SELECT id, parent_id
        FROM "public"."workflows"
        WHERE code = '{step_code}'
    ),
    selected_items AS (
        SELECT ds.item_id
        FROM "public"."document_state" ds
        WHERE ds.workflow_id = (SELECT parent_id FROM step_info)
            AND ds.end_time IS NOT NULL
        ORDER BY ds.end_time ASC
        {limit_clause}
        FOR UPDATE SKIP LOCKED
    )
    UPDATE "public"."document_state" ws
    SET
        workflow_id = (SELECT id FROM step_info),
        start_time = NOW(),
        end_time = NULL
    FROM selected_items si
    WHERE ws.item_id = si.item_id
    RETURNING ws.item_id;
    """

    with conn.cursor() as cur:
        cur.execute(query, tuple(params))

        locked_items = [row[0] for row in cur.fetchall()]

        logger.info(
            f"Đã khóa thành công {len(locked_items)} item(s) cho step_code='{step_code}'."
        )
        return locked_items


def get_workflow_item_counts_via_pipeline(
    pipeline: dlt.Pipeline,
) -> List[Tuple[int, int]]:
    query = """
        SELECT workflow_id, COUNT(*)
        FROM "public"."document_state"
        GROUP BY workflow_id
        ORDER BY workflow_id ASC;
    """

    # logger.info(f"Bắt đầu lấy thống kê từ pipeline: {pipeline.pipeline_name}")

    try:
        with pipeline.sql_client() as client:
            results = client.execute_sql(query)

            if not results:
                print("Không có dữ liệu để hiển thị biểu đồ.")
                return

            logger.success(f"Đã lấy thành công thống kê cho workflow")

            # 4. Xử lý dữ liệu
            # Tách dữ liệu thành 2 danh sách: Trục X (workflow_ids) và Trục Y (counts)
            # Ép kiểu workflow_id sang chuỗi (string) để plotext hiển thị đúng dạng nhãn (label)
            workflow_ids = [str(row[0]) for row in results]
            counts = [row[1] for row in results]

            # 5. Cấu hình và vẽ biểu đồ trên terminal
            plt.clear_figure()  # Xóa bộ đệm biểu đồ cũ (nếu có)
            plt.bar(workflow_ids, counts)

            # Thêm tiêu đề và nhãn trục
            plt.title("Thống Kê Số Lượng Document State Theo Workflow ID")
            plt.xlabel("Workflow ID")
            plt.ylabel("Số Lượng (Count)")

            # Tuỳ chỉnh kích thước biểu đồ (chiều rộng cột text, chiều cao dòng text)
            plt.plotsize(80, 25)

            # Áp dụng giao diện (theme). Có thể thử: 'clear', 'dark', 'pro', ...
            plt.theme("clear")

            # 6. Hiển thị biểu đồ ra màn hình console
            plt.show()

            for workflow_id, count in results:
                logger.debug(f"ID: {workflow_id}, Count: {count}")

            return results

    except Exception as e:
        logger.error(f"Lỗi database khi lấy thống kê workflow: {e}")
        raise


def log_error_workflow_state(
    pipeline: dlt.Pipeline,
    error_item_ids: list,
    start_time: datetime,
    fallback_workflow_id: int = workflow_config.STEP_LOAD_DOCUMENT_LIST.id
    # fallback_workflow_id: int = 0,
):
    if not error_item_ids:
        return

    try:
        pipeline.run(
            document_state_resource(
                workflow_id=fallback_workflow_id,
                item_ids=error_item_ids,
                start_time=start_time,
                end_time=datetime.now(),
            )
        )
        logger.info(
            f"🔄 Đã cập nhật state cho {len(error_item_ids)} items lỗi (Revert về workflow_id={fallback_workflow_id})."
        )
    except Exception as e:
        logger.error(f"❌ Lỗi khi ghi state cho items lỗi: {e}")
