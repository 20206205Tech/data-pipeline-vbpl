import math
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import psycopg2
import scrapy
from loguru import logger
from psycopg2 import Error
from scrapy.utils.response import open_in_browser

import env
from utils.request_helper import make_vbpl_page_request


class DocumentListSpider(scrapy.Spider):
    name = "document_list"
    allowed_domains = ["vbpl.vn"]

    def __init__(self, *args, **kwargs):
        super(DocumentListSpider, self).__init__(*args, **kwargs)

        self.row_per_page = 2 if env.CRAWL_DATA_ENV_DEV else 50
        self.max_pages = 1
        self.determine_crawl_limit()

    def determine_crawl_limit(self):
        connection = None
        try:
            connection = psycopg2.connect(env.DATA_PIPELINE_VBPL_DATABASE_URL)
            cursor = connection.cursor()

            sql_query = f"""
                SELECT total_count
                FROM "public"."document_total"
                ORDER BY update_at DESC
                LIMIT 2;
            """

            cursor.execute(sql_query)
            records = cursor.fetchall()

            diff = 10 if env.CRAWL_DATA_ENV_DEV else 500

            if len(records) >= 2:
                latest = records[0][0]
                previous = records[1][0]

                if latest != previous:
                    diff = abs(latest - previous)
                    logger.info(
                        f"Phát hiện thay đổi: {previous} -> {latest}. Diff = {diff}"
                    )
                else:
                    logger.info(
                        f"Không có thay đổi tổng số. Sử dụng diff mặc định: {diff}"
                    )
            else:
                logger.info(
                    f"Không đủ dữ liệu lịch sử (cần 2 bản ghi). Sử dụng diff mặc định: {diff}"
                )

            self.max_pages = math.ceil(diff / self.row_per_page) + 1

            logger.info(
                f"Kết quả tính toán: max_pages = {self.max_pages} (row_per_page = {self.row_per_page})"
            )

        except (Exception, Error) as error:
            logger.error(
                f"Lỗi khi truy xuất database: {error}. Sử dụng cấu hình dự phòng."
            )
            self.max_pages = 2 if env.CRAWL_DATA_ENV_DEV else 10
        finally:
            if connection:
                cursor.close()
                connection.close()

    def start_requests(self):
        yield make_vbpl_page_request(self, page=1, row_per_page=self.row_per_page)

    def parse(self, response):
        if env.CRAWL_DATA_OPEN_IN_BROWSER:
            open_in_browser(response)

        current_page = response.meta.get("current_page", 1)
        items = response.xpath('//div[@class="item"]')

        if not items:
            logger.warning(
                f"Không tìm thấy dữ liệu tại trang {current_page}. Dừng spider."
            )
            return

        for item in items:
            link_chi_tiet = response.urljoin(item.css("p.title a::attr(href)").get())
            parsed_url = urlparse(link_chi_tiet)
            item_id = parse_qs(parsed_url.query).get("ItemID", [None])[0]

            yield {
                "update_at": datetime.now().isoformat(),
                # 'processing_status': "pending",
                "item_id": item_id,
                # 'so_hieu': ' '.join(item.css('p.title a::text').get(default='').split()),
                # 'trich_yeu': ' '.join(item.css('div.des p::text').get(default='').split()),
                # 'ngay_ban_hanh': item.xpath('.//label[contains(text(), "Ban hành")]/following-sibling::text()').get(default='').replace(':', '').strip(),
                # 'ngay_hieu_luc': item.xpath('.//label[contains(text(), "Hiệu lực")]/following-sibling::text()').get(default='').replace(':', '').strip(),
                # 'trang_thai': item.css('p.red::text').get(default='Còn hiệu lực').strip(),
            }

        if current_page < self.max_pages:
            yield make_vbpl_page_request(
                self, page=current_page + 1, row_per_page=self.row_per_page
            )
