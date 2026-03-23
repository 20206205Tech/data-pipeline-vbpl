from urllib.parse import urlencode

import scrapy
from loguru import logger

import env


def make_vbpl_page_request(spider_instance, page, row_per_page=None):
    if row_per_page is None:
        row_per_page = 10 if env.CRAWL_DATA_ENV_DEV else 50

    base_url = "https://vbpl.vn/VBQPPL_UserControls/Publishing_22/TimKiem/p_KetQuaTimKiemVanBan.aspx"
    headers = {"X-Requested-With": "XMLHttpRequest"}

    params = {
        "IsVietNamese": "True",
        "DivID": "resultSearch",
        "RowPerPage": row_per_page,
        "Page": page,
        "order": "VBPQNgayBanHanh",  # Sắp xếp theo ngày ban hành
        "TypeOfOrder": "False",  # Giảm dần (mới nhất lên đầu)
        "s": "0",  # Tìm tất cả từ khóa
        "type": "0",  # Loại form tìm kiếm
    }

    query_string = urlencode(params)
    url = f"{base_url}?{query_string}"

    logger.debug(f"Đang tạo request cho trang {page}: {url}")

    return scrapy.Request(
        url=url,
        method="POST",
        headers=headers,
        callback=spider_instance.parse,
        meta={"current_page": page},
    )
