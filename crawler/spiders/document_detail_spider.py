import os
from datetime import datetime

import psycopg2
import scrapy
from scrapy.utils.response import open_in_browser

import env
from output_document_detail import PATH_FOLDER_OUTPUT
from utils.workflow_helper import fetch_and_lock_pending_tasks


class DocumentDetailSpider(scrapy.Spider):
    name = "document_detail"
    allowed_domains = ["vbpl.vn"]

    def _get_connection(self):
        return psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

    def start_requests(self):
        limit = 2 if env.CRAWL_DATA_ENV_DEV else 150
        pending_item_ids = []

        conn = None
        try:
            conn = self._get_connection()
            with conn:
                pending_item_ids = fetch_and_lock_pending_tasks(
                    conn=conn,
                    step_code="step_crawl_document_detail",
                    limit=limit,
                )

        except Exception as e:
            self.logger.error(f"Lỗi khi lấy logic database từ PostgreSQL: {e}")
            return
        finally:
            if conn:
                conn.close()

        if not pending_item_ids:
            self.logger.info("🎉 Không còn bản ghi nào cần crawl.")
            return

        for item_id in pending_item_ids:
            url = f"https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={item_id}"

            yield scrapy.Request(
                url=url, callback=self.parse_detail, meta={"item_id": item_id}
            )

    def parse_detail(self, response):
        if env.CRAWL_DATA_OPEN_IN_BROWSER:
            open_in_browser(response)

        item_id = response.meta.get("item_id")

        if response.status == 200:
            # Lấy nội dung text của thẻ title
            page_title = response.xpath("//title/text()").get(default="")

            # Kiểm tra nếu title chứa chữ "Error" và nội dung có "Sorry, something went wrong"
            if "Error" in page_title and "Sorry, something went wrong" in response.text:
                self.logger.warning(
                    f"⚠️ Bỏ qua item {item_id} vì trang web báo lỗi hệ thống (Sorry, something went wrong)."
                )
                return  # Kết thúc xử lý đối với item này

            file_path = os.path.join(PATH_FOLDER_OUTPUT, f"{item_id}.html")
            os.makedirs(PATH_FOLDER_OUTPUT, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            self.logger.info(f"✅ Đã lưu detail: {item_id}")

            yield {
                "update_at": datetime.now().isoformat(),
                "item_id": item_id,
            }
        else:
            self.logger.warning(
                f"❌ Crawl thất bại (Status {response.status}) cho item: {item_id}"
            )
