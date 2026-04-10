import requests

# from langchain_cloudflare import ChatCloudflareWorkersAI
# from langchain_groq import ChatGroq
# from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_ollama import ChatOllama
from loguru import logger

import env

# nvidia_llm = ChatNVIDIA(
#     model="meta/llama-3.1-405b-instruct",
#     api_key=env.NVIDIA_API_KEY,
#     temperature=0.3,
# )

# cloudflare_llm = ChatCloudflareWorkersAI(
#     account_id=env.CLOUDFLARE_ACCOUNT_ID,
#     api_token=env.CLOUDFLARE_API_TOKEN,
#     model="@cf/meta/llama-3.1-8b-instruct",
#     temperature=0.3,
# )

# groq_llm = ChatGroq(
#     api_key=env.GROQ_API_KEY,
#     # Có thể đổi sang "llama-3.1-70b-versatile" nếu cần
#     model_name="llama-3.1-8b-instant",
#     temperature=0.3,
# )

ollama_llm = ChatOllama(
    base_url=env.OLLAMA_URL,
    model="gemma2:9b",
    temperature=0.3,
    num_ctx=32768,
)


def check_ollama_health():
    try:
        response = requests.get(env.OLLAMA_URL, timeout=3)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Lỗi khi kiểm tra sức khỏe Ollama: {e}")
        return False


def invoke_llm_chain(messages):
    # # Cấp 1: Thử NVIDIA
    # try:
    #     logger.info("🚀 Đang gọi NVIDIA...")
    #     res = nvidia_llm.invoke(messages)
    #     return res.content.strip()
    # except Exception as e:
    #     logger.warning(f"⚠️ NVIDIA lỗi: {e}")

    # # Cấp 2: Thử Cloudflare
    # try:
    #     logger.info("☁️ Đang gọi Cloudflare...")
    #     res = cloudflare_llm.invoke(messages)
    #     return res.content.strip()
    # except Exception as e:
    #     logger.warning(f"⚠️ Cloudflare lỗi: {e}")

    # # Cấp 3: Thử Groq
    # try:
    #     logger.info("⚡ Đang gọi Groq...")
    #     res = groq_llm.invoke(messages)
    #     return res.content.strip()
    # except Exception as e:
    #     logger.warning(f"⚠️ Groq lỗi thực thi: {e}")

    # Cấp 4: Thử Ollama (Local Fallback)
    if check_ollama_health():
        try:
            logger.info("🏠 Đang gọi Ollama...")
            res = ollama_llm.invoke(messages)
            return res.content.strip()
        except Exception as e:
            logger.warning(f"⚠️ Ollama lỗi thực thi: {e}")
    else:
        logger.error("❌ Ollama đang Offline.")

    logger.critical("🚨 TẤT CẢ LLM ĐỀU THẤT BẠI!")
    return None
