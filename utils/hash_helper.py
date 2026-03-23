import hashlib

from loguru import logger


def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Lỗi tính hash file {file_path}: {e}")
        return None


def calculate_string_hash(content_string):
    hasher = hashlib.sha256()
    try:
        hasher.update(content_string.encode("utf-8"))
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Lỗi tính hash chuỗi: {e}")
        return None


# def get_existing_hash_from_db(conn, table_name, item_id, file_id_column="drive_id"):
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 f"""
#                 SELECT file_hash, {file_id_column}
#                 FROM "public"."{table_name}"
#                 WHERE item_id = %s
#                 """,
#                 (item_id,),
#             )
#             row = cur.fetchone()
#             if row:
#                 return row[0], row[1]
#     except psycopg2.errors.UndefinedTable:
#         conn.rollback()
#     except Exception as e:
#         logger.debug(f"Lỗi truy vấn hash cũ cho {item_id} ở bảng {table_name}: {e}")
#         conn.rollback()
#     return None, None
