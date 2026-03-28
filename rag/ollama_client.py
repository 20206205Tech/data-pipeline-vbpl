import sys  # Thêm thư viện sys
import time

import requests
from langchain_ollama import ChatOllama
from loguru import logger

import env

llm = ChatOllama(
    base_url=env.OLLAMA_URL,
    # model="qwen2.5:7b",
    model="gemma2:9b",
    temperature=0.3,
    num_ctx=32768,
)


def check_ollama_health():
    try:
        base_url = env.OLLAMA_URL
        response = requests.get(base_url, timeout=10)
        return response.text.strip() == "Ollama is running"
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra trạng thái Ollama: {e}")
        return False


def call_ollama(messages, max_retries=3, stream=True):
    if not check_ollama_health():
        logger.error(
            "❌ Ollama server không phản hồi chính xác 'Ollama is running'. Dừng thực thi."
        )
        # Thoát chương trình ngay lập tức với mã lỗi 1
        sys.exit(1)

    for attempt in range(max_retries):
        try:
            logger.info(f"Đang gửi yêu cầu (Lần {attempt + 1}/{max_retries})...")

            full_content = ""
            if stream:
                for chunk in llm.stream(messages):
                    full_content += chunk.content
                    print(chunk.content, end="", flush=True)
                print("\n")
            else:
                response = llm.invoke(messages)
                full_content = response.content.strip()

            return full_content

        except Exception as e:
            error_str = str(e)
            wait_time = 10
            logger.warning(
                f"⏳ Lỗi kết nối Ollama. Đợi {wait_time}s rồi thử lại (Lần {attempt + 1}/{max_retries}). Chi tiết lỗi: {error_str}"
            )
            time.sleep(wait_time)

    logger.error("❌ Đã thử lại nhiều lần nhưng không thể lấy được phản hồi từ Ollama.")
    return None
