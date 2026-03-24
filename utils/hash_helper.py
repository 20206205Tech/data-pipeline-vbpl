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


def get_existing_drive_id_from_db(conn, table_name, item_id, file_id_column="drive_id"):
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {file_id_column}
                FROM "public"."{table_name}"
                WHERE item_id = %s
                """,
                (str(item_id),),
            )
            row = cur.fetchone()
            if row:
                return row[0]
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
    except Exception as e:
        logger.debug(f"Lỗi truy vấn drive_id cho {item_id} ở bảng {table_name}: {e}")
        conn.rollback()
    return None


def get_existing_hash_from_db(
    conn, table_name, item_id, file_hash_column, file_id_column="drive_id"
):
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {file_hash_column}, {file_id_column}
                FROM "public"."{table_name}"
                WHERE item_id = %s
                """,
                (str(item_id),),
            )
            row = cur.fetchone()
            if row:
                return row[0], row[1]
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
    except Exception as e:
        logger.debug(f"Lỗi truy vấn hash cũ cho {item_id} ở bảng {table_name}: {e}")
        conn.rollback()
    return None, None
