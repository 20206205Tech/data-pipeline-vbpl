# import os
# import re
# import shutil
# from datetime import datetime

# import dlt
# import psycopg2
# from loguru import logger

# import env
# from utils.config_by_path import ConfigByPath
# from utils.google_drive import download_from_drive, get_drive_service, upload_to_drive
# from utils.hash_helper import calculate_file_hash
# from utils.workflow_helper import fetch_and_lock_pending_tasks, log_workflow_state

# config_by_path = ConfigByPath(__file__)


# PATH_FOLDER_OUTPUT = config_by_path.PATH_FOLDER_OUTPUT


# def process_and_chunk(md_text):
#     chunks = re.split(r"(?=\n#|\n\*\*)", md_text)

#     final_sections = []
#     for chunk in chunks:
#         cleaned_chunk = chunk.strip()
#         if cleaned_chunk:
#             final_sections.append(cleaned_chunk)

#     return final_sections


# @dlt.resource(
#     write_disposition="merge",
#     primary_key="item_id",
#     columns={"update_at": {"dedup_sort": "desc"}},
# )
# def document_chunk(item_ids: list):
#     try:
#         drive_service = get_drive_service()

#         conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)
#     except Exception as e:
#         logger.error(f"Lỗi khởi tạo kết nối Database/Drive: {e}")
#         return

#     try:
#         pending_item_ids = fetch_and_lock_pending_tasks(
#             conn=conn,
#             step_code=config_by_path.NAME,
#             limit=10,
#         )

#         if not pending_item_ids:
#             logger.info("🎉 Không có tài liệu Markdown nào cần phân mảnh (chunking).")
#             return

#         for item_id in pending_item_ids:
#             try:
#                 with conn.cursor() as cur:
#                     cur.execute(
#                         f"""
#                             SELECT drive_id, file_hash
#                             FROM "public"."document_markdown"
#                             WHERE item_id = %s
#                         """,
#                         (item_id,),
#                     )
#                     res = cur.fetchone()
#                     if not res:
#                         logger.warning(
#                             f"⚠️ Bỏ qua {item_id}: Không tìm thấy dữ liệu Markdown trong Database."
#                         )
#                         continue
#                     md_drive_id, md_file_hash = res

#                 # 2. Truy vấn lịch sử xử lý Chunking
#                 old_md_hash = None
#                 old_zip_hash = None
#                 old_drive_id = None
#                 try:
#                     with conn.cursor() as cur:
#                         cur.execute(
#                             f"""
#                             SELECT md_hash, zip_hash, drive_id
#                             FROM "public"."document_chunk"
#                             WHERE item_id = %s
#                             """,
#                             (item_id,),
#                         )
#                         row = cur.fetchone()
#                         if row:
#                             old_md_hash, old_zip_hash, old_drive_id = row
#                 except psycopg2.errors.UndefinedTable:
#                     conn.rollback()
#                 except Exception as e:
#                     conn.rollback()
#                     logger.debug(f"Lỗi kiểm tra lịch sử chunking cho {item_id}: {e}")

#                 # 3. Bỏ qua nếu Markdown không thay đổi
#                 if old_md_hash and old_md_hash == md_file_hash:
#                     logger.info(
#                         f"⏭️ Bỏ qua {item_id}: Nội dung Markdown không thay đổi."
#                     )
#                     item_ids.append(item_id)
#                     yield {
#                         "item_id": item_id,
#                         "update_at": datetime.now().isoformat(),
#                         "drive_id": old_drive_id,
#                         "md_hash": md_file_hash,
#                         "zip_hash": old_zip_hash,
#                     }
#                     continue

#                 # 4. Tải file Markdown và thực hiện Chunking theo cấu trúc
#                 logger.info(
#                     f"📝 Đang tải và phân mảnh tài liệu (Markdown Structure): {item_id}"
#                 )
#                 md_bytes = download_from_drive(drive_service, md_drive_id)
#                 md_text = md_bytes.decode("utf-8")

#                 final_sections = process_and_chunk(md_text)

#                 # 5. Tạo cấu trúc thư mục và lưu từng file chunk_x.md
#                 item_folder = os.path.join(PATH_FOLDER_OUTPUT, str(item_id))
#                 os.makedirs(item_folder, exist_ok=True)

#                 for idx, section in enumerate(final_sections):
#                     chunk_path = os.path.join(item_folder, f"chunk_{idx + 1}.md")
#                     with open(chunk_path, "w", encoding="utf-8") as f:
#                         f.write(section)

#                 logger.info(
#                     f"📁 Đã tạo {len(final_sections)} file chunks trong thư mục: {item_folder}"
#                 )

#                 # 6. Nén thư mục thành file ZIP
#                 zip_base_path = os.path.join(PATH_FOLDER_OUTPUT, str(item_id))
#                 shutil.make_archive(zip_base_path, "zip", item_folder)
#                 zip_file_path = f"{zip_base_path}.zip"

#                 # 7. Tính Hash file ZIP
#                 zip_file_hash = calculate_file_hash(zip_file_path)

#                 # 8. Upload ZIP lên Google Drive
#                 logger.info(f"☁️ Đang tải file nén lên Google Drive...")
#                 new_drive_id = upload_to_drive(
#                     drive_service, zip_file_path, config_by_path.GOOGLE_DRIVE_FOLDER_ID_DATA_PIPELINE_VBPL
#                 )

#                 if new_drive_id:
#                     item_ids.append(item_id)
#                     yield {
#                         "item_id": item_id,
#                         "update_at": datetime.now().isoformat(),
#                         "drive_id": new_drive_id,
#                         "md_hash": md_file_hash,  # Cột 1: Hash Input
#                         "zip_hash": zip_file_hash,  # Cột 2: Hash Output (Zip)
#                     }

#             except Exception as e:
#                 logger.error(f"💥 Lỗi tại item {item_id}: {e}")

#     finally:
#         if conn:
#             conn.close()


# if __name__ == "__main__":
#     pipeline = dlt.pipeline(
#         destination="postgres",
#         dataset_name="public",
#         pipeline_name=config_by_path.NAME,
#     )

#     item_ids = []
#     start_time = datetime.now()

#     info = pipeline.run(document_chunk(item_ids))
#     # logger.info(f"Kết quả pipeline: {info}")

#     if item_ids:
#         log_workflow_state(
#             pipeline=pipeline,
#             item_ids=item_ids,
#             start_time=start_time,
#             end_time=datetime.now(),
#         )
