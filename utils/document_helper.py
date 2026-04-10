import psycopg2
from loguru import logger

# Danh sách các trạng thái cần bỏ qua
STATUS_TO_SKIP = [
    "Hết hiệu lực toàn bộ",
    "Ngưng hiệu lực",
    "Không còn phù hợp",
]


def is_document_invalid(status: str) -> bool:
    """
    Kiểm tra xem văn bản có thuộc diện hết hiệu lực/cần bỏ qua hay không.
    """
    if not status:
        return False
    return status.strip() in STATUS_TO_SKIP


def get_document_statuses_from_db(conn, item_ids: list) -> dict:
    """
    Lấy trạng thái (status) từ bảng document_info cho nhiều item cùng lúc.
    Trả về: Dictionary { 'item_id': 'status' }
    """
    if not item_ids:
        return {}

    str_item_ids = tuple(str(id) for id in item_ids)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id, status
                FROM "public"."document_info"
                WHERE item_id IN %s
                """,
                (str_item_ids,),
            )
            rows = cur.fetchall()
            return {str(row[0]): row[1] for row in rows}

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
    except Exception as e:
        logger.debug(f"Lỗi truy vấn status từ bảng document_info: {e}")
        conn.rollback()

    return {}
