from flask import Flask, request, jsonify
import json
import gspread
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from apscheduler.schedulers.background import BackgroundScheduler
import os
import requests
import io

app = Flask(__name__)

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
SPREADSHEET_NAME = "LineMessages"

# 從環境變數讀取憑證內容
credentials_base64 = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
credentials_dict = json.loads(credentials_json)
drive_credentials = Credentials.from_service_account_info(credentials_dict)

# 設定 Google Sheets API 的授權
sheet_credentials = Credentials.from_service_account_file(
    SHEET_CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(sheet_credentials)
sheet = gc.open(SPREADSHEET_NAME).sheet1

# Google Drive API 的資料夾ID
FOLDER_ID = '11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO'

def get_drive_service():
    """登入並返回 Google Drive API 服務對象"""
    service = build('drive', 'v3', credentials=drive_credentials)
    return service

def download_image_from_line(message_id):
    """從 LINE 下載圖片"""
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return io.BytesIO(response.content)
    else:
        print(f"無法下載圖片: {response.status_code}")
        return None

def upload_image_to_drive(image_data, file_name):
    """將下載的圖片上傳到 Google Drive"""
    try:
        service = get_drive_service()
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }
        media = MediaIoBaseUpload(image_data, mimetype='image/jpeg')
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return uploaded_file['id']
    except Exception as e:
        print(f"圖片上傳失敗: {e}")
        return None

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)

    try:
        json_data = json.loads(body)
        if "events" in json_data and len(json_data["events"]) > 0:
            event = json_data["events"][0]
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            message_text = event["message"].get("text", "")

            sheet.append_row([user_id, message_text])

            if message_type == "image":
                message_id = event["message"]["id"]
                image_data = download_image_from_line(message_id)
                if image_data:
                    uploaded_file_id = upload_image_to_drive(image_data, f"{message_id}.jpg")
                    if uploaded_file_id:
                        print(f"圖片已上傳到 Google Drive: {uploaded_file_id}")
                    else:
                        print("圖片上傳失敗")
                else:
                    print("無法下載圖片")

            print(f"接收到事件: {event}")
            return "OK"
        else:
            print("沒有事件需要處理")
            return "No Event", 200

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return "Internal Server Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
