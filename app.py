from flask import Flask, request, jsonify
import json
import gspread
import base64  # 確保有導入 base64 模組
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import io
import datetime
import pytz
from linebot import LineBotApi

app = Flask(__name__)

# LINE Bot API 設定
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
SPREADSHEET_NAME = "LineMessages"
LINE_ID_SPREADSHEET_ID = "1uuIEQdD_maLJFG3Qj-gIPWw5Ph0leRyrOed_LNmOM"

# 從環境變數讀取憑證內容
credentials_base64 = os.getenv("GOOGLE_DRIVE_CREDENTIALS")

# 將 base64 字符串解碼
credentials_json = base64.b64decode(credentials_base64).decode("utf-8")

# 解析 JSON
credentials_dict = json.loads(credentials_json)

# 使用憑證來建立 Google API 認證
drive_credentials = Credentials.from_service_account_info(credentials_dict)

# 設定 Google Sheets API 的授權
sheet_credentials = Credentials.from_service_account_file(
    SHEET_CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(sheet_credentials)

# 開啟 Google Sheets
sheet = gc.open(SPREADSHEET_NAME).sheet1
line_id_sheet = gc.open_by_key(LINE_ID_SPREADSHEET_ID).sheet1

# Google Drive API 的資料夾ID
FOLDER_ID = '11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO'

def get_drive_service():
    """登入並返回 Google Drive API 服務對象"""
    service = build('drive', 'v3', credentials=drive_credentials)
    return service

def get_class_std_from_user_id(user_id):
    """從 LineId 試算表中獲取對應的 class 和 std"""
    records = line_id_sheet.get_all_records()
    for record in records:
        if record['id'] == user_id:
            return record['class'], record['std']
    return None, None

def upload_image_to_drive(image_data, file_name):
    """將圖片內容上傳到 Google Drive"""
    try:
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
        
@app.route("/", methods=["GET"])
def keep_alive():
    return "OK", 200

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature")

    try:
        json_data = json.loads(body)

        if "events" in json_data and len(json_data["events"]) > 0:
            event = json_data["events"][0]
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            message_id = event["message"]["id"]

            # 獲取台灣時間
            taiwan_tz = pytz.timezone("Asia/Taipei")
            taiwan_time = datetime.datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S")

            # 處理文字訊息
            message_text = event["message"].get("text", "")

            if message_type == "text":
                sheet.append_row([taiwan_time, user_id, message_text])

            # 處理圖片訊息
            elif message_type == "image":
                sheet.append_row([taiwan_time, user_id, f"Image ID: {message_id}"])

                # 獲取 class 和 std
                class_name, std_name = get_class_std_from_user_id(user_id)
                file_name = f"{class_name}_{std_name}_{message_id}.jpg" if class_name and std_name else f"{message_id}.jpg"

                # 使用 LineBotApi 下載圖片內容
                message_content = line_bot_api.get_message_content(message_id)
                image_data = io.BytesIO(message_content.content)

                # 將圖片上傳到 Google Drive
                uploaded_file_id = upload_image_to_drive(image_data, file_name)
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
