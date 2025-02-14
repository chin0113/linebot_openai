from flask import Flask, request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import json
import base64

app = Flask(__name__)

# Google Drive 資料夾 ID
FOLDER_ID = "11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO"

# Google Drive 憑證
credentials_base64 = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
credentials_dict = json.loads(credentials_json)
drive_credentials = Credentials.from_service_account_info(credentials_dict)

def upload_to_drive(file_path, file_name):
    """將暫存的圖片上傳到 Google Drive"""
    try:
        service = build("drive", "v3", credentials=drive_credentials)
        file_metadata = {"name": file_name, "parents": [FOLDER_ID]}
        media = MediaFileUpload(file_path, mimetype="image/jpeg")

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        print(f"圖片已上傳到 Google Drive，檔案 ID: {uploaded_file['id']}")
    except Exception as e:
        print(f"圖片上傳失敗: {e}")

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_json()

    if "events" in body and len(body["events"]) > 0:
        event = body["events"][0]

        if event["message"]["type"] == "image":
            message_id = event["message"]["id"]

            # 暫存圖片到 /tmp
            temp_file_path = f"/tmp/{message_id}.jpg"
            message_content = messaging_api_blob.get_message_content(message_id)

            # 將圖片內容寫入暫存檔案
            with open(temp_file_path, "wb") as temp_file:
                for chunk in message_content.iter_content():
                    temp_file.write(chunk)

            print(f"圖片已下載到 {temp_file_path}")

            # 上傳到 Google Drive
            upload_to_drive(temp_file_path, f"{message_id}.jpg")

            return "OK"

    return "No Event", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
