import os

from loguru import logger

import env
from utils.google_drive import get_drive_service, get_or_create_drive_folder


class ConfigByPath:
    def __init__(self, path_file):
        self.NAME = os.path.splitext(os.path.basename(os.path.abspath(path_file)))[0]
        self._path_folder_output = None
        self._drive_folder_id = None

    @property
    def PATH_FOLDER_OUTPUT(self):
        if self._path_folder_output is None:
            path = os.path.join(env.PATH_FOLDER_DATA, self.NAME)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            self._path_folder_output = path
        return self._path_folder_output

    @property
    def PATH_FILE_OUTPUT(self):
        return os.path.join(self.PATH_FOLDER_OUTPUT, "output.jsonl")

    @property
    def GOOGLE_DRIVE_FOLDER_ID_DATA_PIPELINE_VBPL(self):
        if self._drive_folder_id is None:
            try:
                service = get_drive_service()
                self._drive_folder_id = get_or_create_drive_folder(
                    service, self.NAME, env.GOOGLE_DRIVE_FOLDER_ID_DATA_PIPELINE_VBPL
                )
            except Exception as e:
                logger.error(f"Lỗi khi kết nối Google Drive: {e}")
                return None
        return self._drive_folder_id
