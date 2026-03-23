import json

from loguru import logger


def yield_jsonl_records(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Lỗi format JSON tại file {file_path}: {e}")
    except FileNotFoundError:
        logger.error(f"Không tìm thấy file: {file_path}")
    except Exception as e:
        logger.error(f"Lỗi không xác định khi đọc file {file_path}: {e}")
