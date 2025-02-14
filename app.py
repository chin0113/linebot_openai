from flask import Flask, request, jsonify
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from apscheduler.schedulers.background import BackgroundScheduler
import os
import requests
import io

app = Flask(__name__)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
#DRIVE_CREDENTIALS_FILE = "newagent-gfvg-3ab5f6b7023a.json"
SPREADSHEET_NAME = "LineMessages"  # 試算表名稱（請確保你已創建該試算表）

# 從環境變數讀取憑證內容
credentials_base64 = os.getenv("GOOGLE_DRIVE_CREDENTIALS")

# 將 base64 字符串解碼
credentials_json = base64.b64decode(credentials_base64).decode("utf-8")

# 解析 JSON
credentials_dict = json.loads(credentials_json)

# 使用憑證來建立 Google API 認證
DRIVE_CREDENTIALS_FILE = Credentials.from_service_account_info(credentials_dict)

# 現在您可以繼續使用該憑證來連接 Google Drive 或 Google Sheets 等服務

# 設定 Google Sheets API 的授權
sheet_credentials = Credentials.from_service_account_file(
    SHEET_CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(sheet_credentials)

# 開啟 Google Sheets
sheet = gc.open(SPREADSHEET_NAME).sheet1

# Google Drive API 的資料夾ID
FOLDER_ID = '11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO'

# 定時任務: 保持伺服器活躍
def keep_alive():
    print("保持伺服器活躍...")

# 設定定時任務，每10分鐘執行一次
scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', minutes=10)
scheduler.start()

def get_drive_service():
    """登入並返回 Google Drive API 服務對象"""
    creds = Credentials.from_service_account_file(DRIVE_CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive.file"])
    service = build('drive', 'v3', credentials=creds)
    return service

def upload_image_to_drive(image_url, file_name):
    """直接從 URL 下載圖片並上傳到 Google Drive"""
    try:
        # 下載圖片
        response = requests.get(image_url)
        image_data = io.BytesIO(response.content)

        service = get_drive_service()
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }

        # 上傳檔案
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
    signature = request.headers.get("X-Line-Signature")

    try:
        # 解析 LINE 傳入的訊息
        json_data = json.loads(body)
        
        if "events" in json_data and len(json_data["events"]) > 0:
            event = json_data["events"][0]
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            message_text = event["message"].get("text", "")

            # 將 user_id 和訊息寫入 Google 試算表
            sheet.append_row([user_id, message_text])

            # 如果是圖片訊息，處理圖片
            if message_type == "image":
                # 指定要上傳的圖片URL
                image_url = "https://hsinhua.net/composition/%E7%B7%9A%E4%B8%AD%E4%B8%89/%E4%B8%80%E8%B6%9F%E8%B1%90%E5%AF%8C%E4%B9%8B%E6%97%85/orig/1-1%E6%9D%8E%E5%A6%8D%E6%9B%A6.jpg"
                
                # 打印圖片的 URL
                print(f"圖片網址: {image_url}")

                # 上傳圖片到 Google Drive
                uploaded_file_id = upload_image_to_drive(image_url, "1-1李妍曦.jpg")

                if uploaded_file_id:
                    print(f"圖片已上傳到 Google Drive: {uploaded_file_id}")
                else:
                    print("圖片上傳失敗")

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
