import io
import json
import mimetypes
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from loguru import logger

import env

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    creds = None

    creds_info = json.loads(env.GOOGLE_DRIVE_TOKEN)
    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            logger.error(f"Không thể refresh token: {e}")
            creds = None

    if not creds:
        raise Exception(
            "Không tìm thấy thông tin xác thực! Hãy chạy lấy token tại local trước."
        )

    return build("drive", "v3", credentials=creds)


def get_or_create_drive_folder(service, folder_name, parent_id=None):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    response = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)")
        .execute()
    )
    files = response.get("files", [])

    if files:
        folder_id = files[0]["id"]
        logger.info(f"Folder '{folder_name}' đã tồn tại | ID: {folder_id}")
        return folder_id
    else:
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        file = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = file.get("id")
        logger.info(f"Đã tạo folder mới '{folder_name}' | ID: {folder_id}")
        return folder_id


def upload_to_drive(service, file_path, folder_id):
    try:
        file_name = os.path.basename(file_path)
        file_metadata = {"name": file_name, "parents": [folder_id]}

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        logger.info(f"Đang upload: {file_name} (MimeType: {mime_type})")

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        drive_id = file.get("id")
        logger.success(f"✅ File uploaded: {file_name} | ID: {drive_id}")
        logger.debug(f"Link: {get_drive_url(drive_id)}")

        return drive_id
    except Exception as e:
        logger.error(f"❌ Lỗi khi upload file {file_path}: {e}")
        return None


def get_drive_url(drive_id, is_folder=False):
    if is_folder:
        return f"https://drive.google.com/drive/folders/{drive_id}"
    return f"https://drive.google.com/file/d/{drive_id}/view"


def download_from_drive(service, file_id):
    file_url = get_drive_url(file_id)
    logger.debug(f"Đang tải file từ URL: {file_url}")

    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    return fh.getvalue()


def get_drive_file_md5(drive_service, file_id):
    try:
        file_metadata = (
            drive_service.files().get(fileId=file_id, fields="md5Checksum").execute()
        )
        return file_metadata.get("md5Checksum")
    except Exception as e:
        logger.error(f"Lỗi lấy md5Checksum từ Google Drive cho file {file_id}: {e}")
        return None
