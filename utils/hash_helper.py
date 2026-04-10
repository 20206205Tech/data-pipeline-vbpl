import hashlib

import psycopg2
from loguru import logger


def calculate_file_md5(file_path):
    hasher = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Lỗi tính MD5 file {file_path}: {e}")
        return None


def get_existing_drive_ids_from_db(
    conn, table_name, item_ids, file_id_column="drive_id"
):
    if not item_ids:
        return {}

    # Ép kiểu tất cả item_ids sang string và đưa vào tuple để psycopg2 xử lý mệnh đề IN
    str_item_ids = tuple(str(id) for id in item_ids)

    try:
        with conn.cursor() as cur:
            # Lưu ý: Query SELECT cả item_id và file_id_column để map dữ liệu
            cur.execute(
                f"""
                SELECT item_id, {file_id_column}
                FROM "public"."{table_name}"
                WHERE item_id IN %s
                """,
                (str_item_ids,),
            )
            rows = cur.fetchall()

            # Chuyển đổi danh sách kết quả thành Dictionary
            # row[0] là item_id, row[1] là file_id_column (drive_id)
            return {str(row[0]): row[1] for row in rows}

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
    except Exception as e:
        logger.debug(
            f"Lỗi truy vấn {file_id_column} hàng loạt ở bảng {table_name}: {e}"
        )
        conn.rollback()

    return {}


def get_existing_hashes_from_db(
    conn, table_name, item_ids, file_hash_column, file_id_column="drive_id"
):
    if not item_ids:
        return {}

    str_item_ids = tuple(str(id) for id in item_ids)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT item_id, {file_hash_column}, {file_id_column}
                FROM "public"."{table_name}"
                WHERE item_id IN %s
                """,
                (str_item_ids,),
            )
            rows = cur.fetchall()
            # Trả về dict: key = item_id, value = tuple(hash, drive_id)
            return {str(row[0]): (row[1], row[2]) for row in rows}

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
    except Exception as e:
        logger.debug(f"Lỗi truy vấn hash hàng loạt ở bảng {table_name}: {e}")
        conn.rollback()

    return {}
