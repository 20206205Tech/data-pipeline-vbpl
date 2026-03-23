from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

import env
from crawler.spiders.document_list_spider import DocumentListSpider
from output_document_list import PATH_FILE_OUTPUT


def main():
    settings = get_project_settings()

    custom_settings = {
        "TELNETCONSOLE_ENABLED": False,
        # AutoThrottle (Crawl một cách lịch sự)
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5,
        "AUTOTHROTTLE_MAX_DELAY": 60,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "AUTOTHROTTLE_DEBUG": False,
        "DOWNLOADER_MIDDLEWARES": {
            # Tắt middleware mặc định của Scrapy
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            # Kích hoạt middleware của thư viện
            "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": 400,
        },
        "FEEDS": {
            PATH_FILE_OUTPUT: {"format": "jsonl", "overwrite": True, "encoding": "utf8"}
        },
    }

    if env.CRAWL_DATA_ENV_DEV:
        dev_extra_settings = {
            # Cache (Giảm tải cho server và tăng tốc crawl lại)
            "HTTPCACHE_ENABLED": True,
            "HTTPCACHE_EXPIRATION_SECS": 60 * 60 * 24 * 7,  # 1 tuần
            "HTTPCACHE_DIR": "httpcache",
            "HTTPCACHE_IGNORE_HTTP_CODES": [x for x in range(100, 600) if x != 200],
            "HTTPCACHE_STORAGE": "scrapy.extensions.httpcache.FilesystemCacheStorage",
        }
        custom_settings.update(dev_extra_settings)

        # Kích hoạt thêm HttpCacheMiddleware vào DOWNLOADER_MIDDLEWARES mà không làm mất UserAgent middleware
        custom_settings["DOWNLOADER_MIDDLEWARES"][
            "scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware"
        ] = 900

    settings.update(custom_settings)

    process = CrawlerProcess(settings)
    process.crawl(DocumentListSpider)
    process.start()


if __name__ == "__main__":
    main()
