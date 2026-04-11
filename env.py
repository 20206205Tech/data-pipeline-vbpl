import os

from environs import Env
from loguru import logger

# log_file_format = "{time:YYYY-MM-DD}.log"
# logger.add(
#     f"logging/{log_file_format}", rotation="00:00", retention="7 days", enqueue=True
# )


env = Env()
logger.info("Loading environment variables...")


ENVIRONMENT = env.str("ENVIRONMENT", "production")


PATH_FILE_ENV = os.path.abspath(__file__)
PATH_FOLDER_PROJECT = os.path.dirname(PATH_FILE_ENV)
PATH_FOLDER_DATA = os.path.join(PATH_FOLDER_PROJECT, "data")
PATH_FOLDER_DOCS = os.path.join(PATH_FOLDER_PROJECT, "docs")


if not os.path.exists(PATH_FOLDER_DATA):
    os.makedirs(PATH_FOLDER_DATA)

if not os.path.exists(PATH_FOLDER_DOCS):
    os.makedirs(PATH_FOLDER_DOCS)


CRAWL_DATA_ENV_DEV = False
CRAWL_DATA_OPEN_IN_BROWSER = False

# if ENVIRONMENT == "development":
#     CRAWL_DATA_ENV_DEV = True
#     CRAWL_DATA_OPEN_IN_BROWSER = True


os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"


PINECONE_API_KEY = env.str("PINECONE_API_KEY")
PINECONE_INDEX_NAME = env.str("PINECONE_INDEX_NAME", default="vbpl")


DATA_PIPELINE_VBPL_DATABASE_URL = env.str("DATA_PIPELINE_VBPL_DATABASE_URL")
# if CRAWL_DATA_ENV_DEV:
#     DATA_PIPELINE_VBPL_DATABASE_URL = (
#         "postgresql://postgres:postgres@localhost:5432/postgres"
#     )
DESTINATION__POSTGRES__CREDENTIALS = DATA_PIPELINE_VBPL_DATABASE_URL.replace(
    "-pooler", ""
)
os.environ["DESTINATION__POSTGRES__CREDENTIALS"] = DESTINATION__POSTGRES__CREDENTIALS


GOOGLE_DRIVE_TOKEN = env.str("GOOGLE_DRIVE_TOKEN")
GOOGLE_DRIVE_FOLDER_ID = env.str("GOOGLE_DRIVE_FOLDER_ID")


OLLAMA_URL = "https://ollama.20206205.tech"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_URL = "https://colab.20206205.tech"

WEBHOOK_OLLAMA_URL = "https://webhook.20206205.tech/send-data"


# print("*" * 100)
# for key, value in list(globals().items()):
#     if key.isupper():
#         logger.info(f"{key}: ***")
# print("*" * 100)


NVIDIA_API_KEY = env.str("NVIDIA_API_KEY")


CLOUDFLARE_ACCOUNT_ID = env.str("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = env.str("CLOUDFLARE_API_TOKEN")

GROQ_API_KEY = env.str("GROQ_API_KEY")
