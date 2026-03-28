import os
import sys
from datetime import datetime

import psycopg2
import scrapy
from loguru import logger
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.utils.response import open_in_browser
from twisted.internet.error import TCPTimedOutError, TimeoutError

import env
from output_document_detail import PATH_FOLDER_OUTPUT
from utils.workflow_helper import fetch_and_lock_pending_tasks


class DocumentDetailSpider(scrapy.Spider):
    name = "document_detail"
    allowed_domains = ["vbpl.vn"]

    def _get_connection(self):
        return psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)

    def start_requests(self):
        pending_item_ids = []
        conn = None
        try:
            conn = self._get_connection()
            with conn:
                pending_item_ids = fetch_and_lock_pending_tasks(
                    conn=conn,
                    step_code="step_crawl_document_detail",
                    limit=2 if env.CRAWL_DATA_ENV_DEV else 150,
                )
        except Exception as e:
            logger.error(f"Lỗi khi lấy logic database từ PostgreSQL: {e}")
            return
        finally:
            if conn:
                conn.close()

        if not pending_item_ids:
            logger.info("🎉 Không còn bản ghi nào cần crawl.")
            return

        for item_id in pending_item_ids:
            url = f"https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={item_id}"

            yield scrapy.Request(
                url=url,
                callback=self.parse_detail,
                errback=self.handle_error,
                meta={"item_id": item_id},
            )

    def handle_error(self, failure):
        item_id = failure.request.meta.get("item_id")
        logger.error(f"❌ Lỗi Request tại item {item_id}: {repr(failure)}")

        # Kiểm tra nếu lỗi là do quá hạn 2 phút (Timeout)
        if failure.check(TimeoutError, TCPTimedOutError):
            logger.error(
                "🛑 Website không phản hồi sau 2 phút! Đang hủy bỏ tất cả các URL còn lại..."
            )
            self.crawler.engine.close_spider(self, "server_timeout")
            sys.exit(1)

        if failure.check(HttpError):
            response = failure.value.response
            if response.status >= 500:
                logger.error(
                    f"🛑 Server trả về mã lỗi {response.status}! Đang hủy bỏ tất cả các URL còn lại..."
                )
                self.crawler.engine.close_spider(
                    self, f"server_error_{response.status}"
                )
                sys.exit(1)

    def parse_detail(self, response):
        if env.CRAWL_DATA_OPEN_IN_BROWSER:
            open_in_browser(response)

        item_id = response.meta.get("item_id")

        if response.status == 200:
            page_title = response.xpath("//title/text()").get(default="")

            if "Error" in page_title and "Sorry, something went wrong" in response.text:
                logger.warning(
                    f"⚠️ Bỏ qua item {item_id} vì trang web báo lỗi hệ thống (Sorry, something went wrong)."
                )
                # Dừng toàn bộ chương trình khi gặp dòng chữ này
                self.crawler.engine.close_spider(self, "website_content_error")
                sys.exit(1)

            file_path = os.path.join(PATH_FOLDER_OUTPUT, f"{item_id}.html")
            os.makedirs(PATH_FOLDER_OUTPUT, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            logger.info(f"✅ Đã lưu detail: {item_id}")

            yield {
                "update_at": datetime.now().isoformat(),
                "item_id": item_id,
            }
        else:
            logger.warning(
                f"❌ Crawl thất bại (Status {response.status}) cho item: {item_id}"
            )
