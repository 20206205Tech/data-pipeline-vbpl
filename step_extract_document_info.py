import re
from datetime import datetime

import dlt
import psycopg2
from bs4 import BeautifulSoup
from loguru import logger

import env
from utils.config_by_path import ConfigByPath
from utils.google_drive import download_from_drive, get_drive_service
from utils.hash_helper import get_existing_drive_ids_from_db
from utils.workflow_helper import (
    fetch_and_lock_pending_tasks,
    log_error_workflow_state,
    log_workflow_state,
)

config_by_path = ConfigByPath(__file__)


def parse_vietnamese_date(date_str):
    """Convert 'ngày 15 tháng 03 năm 2026' hoặc '15/03/2026' sang dạng date"""
    if not date_str:
        return None
    try:
        # Trường hợp: ngày 15 tháng 03 năm 2026
        match = re.search(r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", date_str)
        if match:
            day, month, year = match.groups()
            return datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()

        # Trường hợp: 15/03/2026
        match_simple = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
        if match_simple:
            return datetime.strptime(match_simple.group(), "%d/%m/%Y").date()
    except Exception:
        pass
    return None


def extract_metadata_from_html(item_id, html_content):
    """Trích xuất metadata từ nội dung HTML string"""
    try:
        if not html_content:
            raise ValueError("Nội dung HTML trống.")

        soup = BeautifulSoup(html_content, "lxml")

        metadata = {
            "item_id": item_id,
            "status": None,
            "effective_date": None,
            "issuing_agency": None,
            "document_number": None,
            "issue_date": None,
            "title": None,
            "signer": None,
            "position": None,
        }

        # 1. Thông tin hiệu lực
        vb_info = soup.find("div", class_="vbInfo")
        if vb_info:
            status = vb_info.find("li", class_="red")
            if status:
                metadata["status"] = (
                    status.get_text(strip=True).replace("Hiệu lực:", "").strip()
                )

            eff_date = vb_info.find("li", class_="green")
            if eff_date:
                raw_eff_date = (
                    eff_date.get_text(strip=True)
                    .replace("Ngày có hiệu lực:", "")
                    .strip()
                )
                metadata["effective_date"] = parse_vietnamese_date(raw_eff_date)

        # 2. Cơ quan ban hành & Số hiệu
        header_table = soup.find("table")
        if header_table:
            cells = header_table.find_all("td")
            if cells:
                cell_text = cells[0].get_text(separator="|", strip=True)
                parts = [p.strip() for p in cell_text.split("|") if p.strip()]
                if parts:
                    metadata["issuing_agency"] = parts[0]
                for p in parts:
                    if "Số:" in p:
                        metadata["document_number"] = p.replace("Số:", "").strip()

        # 3. Ngày ban hành
        date_pattern = re.compile(r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}")
        date_elem = soup.find(string=date_pattern)
        if date_elem:
            metadata["issue_date"] = parse_vietnamese_date(date_elem.strip())

        # 4. Tiêu đề văn bản
        keywords = ["LUẬT", "NGHỊ ĐỊNH", "THÔNG TƯ", "QUYẾT ĐỊNH", "CHỈ THỊ"]
        for tag in soup.find_all(["b", "strong", "p"]):
            text = tag.get_text(strip=True)
            if any(keyword in text.upper() for keyword in keywords):
                if len(text) > 15:
                    metadata["title"] = text
                    break

        # 5. Người ký & Chức vụ
        signer_table = soup.find("table", class_="table_cqbh_cd_nk")
        if signer_table:
            valid_texts = [
                row.get_text(strip=True)
                for row in signer_table.find_all("tr")
                if row.get_text(strip=True) and row.get_text(strip=True) != "(Đã ký)"
            ]
            if len(valid_texts) >= 2:
                metadata["position"] = valid_texts[0]
                metadata["signer"] = valid_texts[-1]

        # 6. KIỂM TRA ĐỊNH DẠNG FILE
        core_fields = [
            metadata["title"],
            metadata["document_number"],
            metadata["issuing_agency"],
        ]
        if not any(core_fields):
            raise ValueError(
                f"File không đúng định dạng. Không thể tìm thấy dữ liệu cấu trúc cho item {item_id}."
            )

        return metadata

    except ValueError as ve:
        raise ve
    except Exception as e:
        logger.error(f"Lỗi parse item {item_id}: {e}")
        return None


@dlt.resource(
    name="document_info",
    write_disposition="merge",
    primary_key="item_id",
    columns={"update_at": {"dedup_sort": "desc"}},
)
def document_info_resource(success_item_ids: list, error_item_ids: list):
    try:
        drive_service = get_drive_service()
        conn = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

        pending_item_ids = fetch_and_lock_pending_tasks(
            conn=conn,
            step_code=config_by_path.NAME,
            limit=300,
        )

        if not pending_item_ids:
            logger.info("🎉 Không có dữ liệu mới cần trích xuất thông tin.")
            return

        dict_drive_ids = get_existing_drive_ids_from_db(
            conn, "document_detail", pending_item_ids, "drive_id"
        )

        for item_id in pending_item_ids:
            try:
                drive_id = dict_drive_ids.get(str(item_id))

                if not drive_id:
                    logger.warning(
                        f"Bỏ qua {item_id}: Không tìm thấy drive_id trong document_detail."
                    )
                    error_item_ids.append(item_id)
                    continue

                logger.info(f"Đang xử lý trích xuất info cho: {item_id}")

                html_bytes = download_from_drive(drive_service, drive_id)
                html_content = html_bytes.decode("utf-8")

                if (
                    "Error" in html_content
                    and "Sorry, something went wrong" in html_content
                ):
                    logger.warning(
                        f"⚠️ Phát hiện lỗi tại item {item_id}. Đánh dấu để thu thập lại."
                    )
                    error_item_ids.append(item_id)
                    continue

                metadata = extract_metadata_from_html(item_id, html_content)

                if metadata:
                    metadata["update_at"] = datetime.now().isoformat()
                    success_item_ids.append(item_id)
                    yield metadata
                else:
                    logger.warning(f"Không trích xuất được metadata cho {item_id}")

            except ValueError as ve:
                logger.error(f"LỖI ĐỊNH DẠNG: {ve}")
                error_item_ids.append(item_id)
            except Exception as e:
                logger.error(f"Lỗi hệ thống khi xử lý item {item_id}: {e}")
                error_item_ids.append(item_id)

    except Exception as e:
        logger.error(f"Lỗi khi truy vấn lấy dữ liệu từ DB: {e}")
    finally:
        if conn:
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

    pipeline.run(document_info_resource(success_item_ids, error_item_ids))

    if success_item_ids:
        log_workflow_state(
            pipeline=pipeline,
            item_ids=success_item_ids,
            start_time=start_time,
            end_time=datetime.now(),
        )
        logger.info(f"Đã xử lý thành công {len(success_item_ids)} items.")

    if error_item_ids:
        logger.error(f"Có {len(error_item_ids)} items gặp lỗi và cần thu thập lại.")
        logger.warning(f"Danh sách lỗi: {error_item_ids}")

        log_error_workflow_state(pipeline, error_item_ids, start_time)

    # get_workflow_item_counts_via_pipeline(pipeline)


if __name__ == "__main__":
    main()
