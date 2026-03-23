from datetime import datetime

import scrapy
from loguru import logger
from scrapy.utils.response import open_in_browser

import env
from utils.request_helper import make_vbpl_page_request


class DocumentTotalSpider(scrapy.Spider):
    name = "document_total"
    allowed_domains = ["vbpl.vn"]

    def start_requests(self):
        yield make_vbpl_page_request(self, page=1, row_per_page=10)

    def parse(self, response):
        if env.CRAWL_DATA_OPEN_IN_BROWSER:
            open_in_browser(response)

        total_text = response.css("div.message strong::text").get()

        if total_text:
            try:
                web_total = int(total_text.strip().replace(".", ""))
                logger.info(f"Tổng số văn bản hiện tại trên Web: {web_total}")

                yield {
                    "update_at": datetime.now().isoformat(),
                    "total_count": web_total,
                }
            except ValueError as e:
                logger.error(f"Lỗi khi chuyển đổi total_count: {e}")
        else:
            logger.warning(
                "Không tìm thấy thông tin tổng số văn bản (div.message strong)"
            )
