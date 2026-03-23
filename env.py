import os

from environs import Env
from loguru import logger

env = Env()
logger.info(f"Loading environment variables...")


PATH_FILE_ENV = os.path.abspath(__file__)
PATH_FOLDER_PROJECT = os.path.dirname(PATH_FILE_ENV)
PATH_FOLDER_DATA = os.path.join(PATH_FOLDER_PROJECT, "data")
PATH_FOLDER_DOCS = os.path.join(PATH_FOLDER_PROJECT, "docs")


if not os.path.exists(PATH_FOLDER_DATA):
    os.makedirs(PATH_FOLDER_DATA)

if not os.path.exists(PATH_FOLDER_DOCS):
    os.makedirs(PATH_FOLDER_DOCS)


CRAWL_DATA_ENV_DEV = env.bool("CRAWL_DATA_ENV_DEV", default=False)
CRAWL_DATA_OPEN_IN_BROWSER = env.bool("CRAWL_DATA_OPEN_IN_BROWSER", default=False)

if CRAWL_DATA_ENV_DEV:
    CRAWL_DATA_OPEN_IN_BROWSER = False


VECTOR_DATABASE_URL = env.str("VECTOR_DATABASE_URL")


DATA_PIPELINE_VBPL_DATABASE_URL = env.str("DATA_PIPELINE_VBPL_DATABASE_URL")
if CRAWL_DATA_ENV_DEV:
    DATA_PIPELINE_VBPL_DATABASE_URL = (
        "postgresql://postgres:postgres@localhost:5432/postgres"
    )
DESTINATION__POSTGRES__CREDENTIALS = DATA_PIPELINE_VBPL_DATABASE_URL.replace(
    "-pooler", ""
)
os.environ["DESTINATION__POSTGRES__CREDENTIALS"] = DESTINATION__POSTGRES__CREDENTIALS


GOOGLE_DRIVE_TOKEN = env.str("GOOGLE_DRIVE_TOKEN")
GOOGLE_DRIVE_FOLDER_ID = env.str("GOOGLE_DRIVE_FOLDER_ID")


# GEMINI_API_KEY = env.str("GEMINI_API_KEY")
# NVIDIA_API_KEY = env.str("NVIDIA_API_KEY")
# CLOUDFLARE_ACCOUNT_ID = env.str("CLOUDFLARE_ACCOUNT_ID")
# CLOUDFLARE_API_TOKEN = env.str("CLOUDFLARE_API_TOKEN")

OLLAMA_URL = "https://ollama.20206205.tech"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_URL = "https://colab.20206205.tech"


# # CRAWL_DATA_VBPL_DATABASE_URL = env.str("CRAWL_DATA_VBPL_DATABASE_URL")
# CRAWL_DATA_VBPL_GOOGLE_DRIVE_DETAIL_FOLDER_ID = env.str(
#     "CRAWL_DATA_VBPL_GOOGLE_DRIVE_DETAIL_FOLDER_ID"
# )


print("*" * 100)
for key, value in list(globals().items()):
    if key.isupper():
        logger.info(f"{key}: ***")
print("*" * 100)
