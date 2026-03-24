import json
import os
import socket
import time
from datetime import datetime

import dlt
import psycopg2
from loguru import logger

import env
import workflow_config
from utils.google_drive import get_drive_file_md5, get_drive_service

# Ép thời gian chờ tối đa cho mọi request mạng là 60 giây
socket.setdefaulttimeout(60)

LIST_FOLDER_ID = env.LIST_FOLDER_ID


def get_existing_data(conn):
    """Lấy danh sách item_id và drive_id cũ từ database"""
    existing_data = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ds.item_id, dd.drive_id
            FROM "public"."document_state" ds
            LEFT JOIN "public"."document_detail" dd ON ds.item_id::text = dd.item_id::text
        """
        )
        for row in cur.fetchall():
            existing_data[str(row[0])] = row[1]
    return existing_data


@dlt.resource(
    name="document_detail",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def detail_resource(sync_data):
    """Cập nhật hoặc thêm mới vào document_detail"""
    for item in sync_data:
        yield {
            "item_id": item["item_id"],
            "update_at": datetime.now().isoformat(),
            "drive_id": item["new_drive_id"],
        }


@dlt.resource(name="document_state", write_disposition="merge", primary_key="item_id")
def state_resource(sync_data):
    """Cập nhật workflow_id cho TẤT CẢ các item được đồng bộ (cả mới và cũ)"""
    for item in sync_data:
        yield {
            "item_id": item["item_id"],
            "workflow_id": workflow_config.STEP_LOAD_DOCUMENT_DETAIL.id,
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "workflow_version": workflow_config.workflow_version,
        }


def main():
    if not LIST_FOLDER_ID:
        logger.error("Danh sách LIST_FOLDER_ID trống. Vui lòng kiểm tra lại cấu hình.")
        return

    drive_service = get_drive_service()
    conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

    logger.info("Đang tải dữ liệu từ Database lên RAM...")
    existing_data = get_existing_data(conn)
    logger.info(f"Đã tải {len(existing_data)} bản ghi.")

    sync_data = []
    scanned_count = 0
    token_file = "resume_token.json"

    start_folder_idx = 0
    page_token = None

    # Khôi phục trạng thái nếu có
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                state = json.load(f)
                start_folder_idx = state.get("folder_idx", 0)
                page_token = state.get("page_token", None)
            logger.info(
                f"🔄 Khôi phục quét từ thư mục thứ {start_folder_idx + 1}/{len(LIST_FOLDER_ID)}..."
            )
        except Exception as e:
            logger.warning(
                f"Không thể đọc file trạng thái: {e}. Sẽ bắt đầu quét từ đầu."
            )

    # Tập hợp theo dõi các ID ĐÃ XỬ LÝ trong lần chạy này để tránh trùng lặp giữa các folder
    processed_items_this_run = set()
    has_error = False

    for folder_idx in range(start_folder_idx, len(LIST_FOLDER_ID)):
        current_folder_id = LIST_FOLDER_ID[folder_idx]
        logger.info(
            f"🚀 Bắt đầu quét thư mục {folder_idx + 1}/{len(LIST_FOLDER_ID)} - ID: {current_folder_id}"
        )

        while True:
            try:
                response = (
                    drive_service.files()
                    .list(
                        q=f"'{current_folder_id}' in parents and trashed=false",
                        spaces="drive",
                        fields="nextPageToken, files(id, name, md5Checksum)",
                        pageSize=1000,
                        pageToken=page_token,
                    )
                    .execute(num_retries=3)
                )

                files = response.get("files", [])

                for file in files:
                    file_name = file.get("name")
                    if not file_name.endswith(".html"):
                        continue

                    # --- BẮT ĐẦU ĐOẠN SỬA LỖI ---
                    raw_id = file_name.replace(".html", "").strip()
                    # Cắt chuỗi theo dấu cách và lấy phần đầu tiên (Ví dụ: "1534 (1)" -> "1534")
                    item_id = raw_id.split(" ")[0]

                    # Bỏ qua nếu ID sau khi làm sạch vẫn không phải là số hợp lệ
                    if not item_id.isdigit():
                        logger.warning(
                            f"Bỏ qua file rác không đúng định dạng ID: {file_name}"
                        )
                        continue
                    # --- KẾT THÚC ĐOẠN SỬA LỖI ---

                    # BỘ LỌC CHỐNG TRÙNG LẶP LIÊN FOLDER
                    if item_id in processed_items_this_run:
                        continue
                    processed_items_this_run.add(item_id)

                    new_drive_id = file.get("id")
                    new_md5 = file.get("md5Checksum")
                    scanned_count += 1

                    # TRƯỜNG HỢP 1: Chưa có trong document_state -> Thêm mới hoàn toàn
                    if item_id not in existing_data:
                        sync_data.append(
                            {
                                "item_id": item_id,
                                "new_drive_id": new_drive_id,
                                "is_new": True,
                            }
                        )
                    # TRƯỜNG HỢP 2: Đã có trong document_state
                    else:
                        old_drive_id = existing_data[item_id]

                        # Nếu có state nhưng mất detail -> Cập nhật detail
                        if not old_drive_id:
                            sync_data.append(
                                {
                                    "item_id": item_id,
                                    "new_drive_id": new_drive_id,
                                    "is_new": False,
                                }
                            )
                            continue

                        # Nếu ID giống hệt nhau (cùng 1 file vật lý trên Drive) -> Bỏ qua
                        if old_drive_id == new_drive_id:
                            continue

                        # Gọi API lấy mã MD5 của file cũ trên Drive để so sánh
                        old_md5 = get_drive_file_md5(drive_service, old_drive_id)

                        if old_md5 != new_md5:
                            logger.info(
                                f"Phát hiện nội dung thay đổi tại item_id: {item_id}"
                            )
                            sync_data.append(
                                {
                                    "item_id": item_id,
                                    "new_drive_id": new_drive_id,
                                    "is_new": False,
                                }
                            )

                page_token = response.get("nextPageToken", None)

                if scanned_count > 0 and scanned_count % 5000 == 0:
                    logger.info(f"Đã quét qua {scanned_count} files unique...")

                # Ghi lại trạng thái sau mỗi lượt 1000 items
                with open(token_file, "w") as f:
                    json.dump({"folder_idx": folder_idx, "page_token": page_token}, f)

                if not page_token:
                    break  # Hoàn tất thư mục hiện tại

                time.sleep(0.5)  # Làm mát kết nối

            except Exception as e:
                logger.error(
                    f"❌ Kết nối bị gián đoạn tại mốc {scanned_count} files. Chi tiết: {e}"
                )
                logger.info(
                    "Trạng thái đã được lưu. Dừng quá trình quét và bắt đầu đồng bộ dữ liệu đã thu thập."
                )
                has_error = True
                break

        # Nếu có lỗi mạng từ vòng lặp while, thoát luôn vòng lặp for để chạy đồng bộ
        if has_error:
            break

        # Reset page_token để chuẩn bị quét folder tiếp theo
        page_token = None

    # Quét hoàn tất mọi thư mục mà không có lỗi -> Xóa file token
    if not has_error and not page_token:
        if os.path.exists(token_file):
            os.remove(token_file)

    conn.close()

    if sync_data:
        logger.info(f"Đang đồng bộ {len(sync_data)} bản ghi vào Database...")
        pipeline = dlt.pipeline(
            destination="postgres",
            dataset_name="public",
            pipeline_name="step_sync_drive_html",
        )
        info = pipeline.run([detail_resource(sync_data), state_resource(sync_data)])
        logger.info(f"Kết quả pipeline: {info}")
    else:
        logger.info("🎉 Tất cả dữ liệu đều đã được đồng bộ, không có sự sai khác!")


if __name__ == "__main__":
    main()
