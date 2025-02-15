from flask import Flask, request, jsonify
import json
import gspread
import base64  # 確保有導入 base64 模組
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import io
from linebot import LineBotApi

app = Flask(__name__)

# LINE Bot API 設定
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
SPREADSHEET_NAME = "LineMessages"
LINE_ID_SHEET_ID = "1uuIEQdD_maLJFG3Qj-gIPWw0w5Ph0leRyrOed_LNmOM"

# 從環境變數讀取憑證內容
credentials_base64 = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
credentials_dict = json.loads(credentials_json)

drive_credentials = Credentials.from_service_account_info(credentials_dict)
sheet_credentials = Credentials.from_service_account_file(
    SHEET_CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(sheet_credentials)

# 開啟 Google Sheets
sheet = gc.open(SPREADSHEET_NAME).sheet1
line_id_sheet = gc.open_by_key(LINE_ID_SHEET_ID).sheet1

# Google Drive API 的資料夾ID
FOLDER_ID = '11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO'

def get_drive_service():
    """登入並返回 Google Drive API 服務對象"""
    return build('drive', 'v3', credentials=drive_credentials)

def upload_image_to_drive(image_data, file_name):
    """將圖片內容上傳到 Google Drive"""
    try:
        service = get_drive_service()
        file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(image_data, mimetype='image/jpeg')
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return uploaded_file['id']
    except Exception as e:
        print(f"圖片上傳失敗: {e}")
        return None

def get_std_from_user_id(user_id):
    """根據 userId 查找對應的 std"""
    try:
        records = line_id_sheet.get_all_records()
        for record in records:
            if record.get("id") == user_id:
                return record.get("std")
    except Exception as e:
        print(f"讀取 Google Sheet 失敗: {e}")
    return None

@app.route("/", methods=["GET"])
def keep_alive():
    return "OK", 200

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)
    try:
        json_data = json.loads(body)
        if "events" in json_data and len(json_data["events"]) > 0:
            event = json_data["events"][0]
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            message_id = event["message"]["id"]
            
            if message_type == "text":
                message_text = event["message"].get("text", "")
                sheet.append_row([user_id, message_text])

            elif message_type == "image":
                sheet.append_row([user_id, f"Image ID: {message_id}"])
                message_content = line_bot_api.get_message_content(message_id)
                image_data = io.BytesIO(message_content.content)
                
                # 取得對應的 std
                std_value = get_std_from_user_id(user_id)
                if std_value:
                    file_name = f"{std_value}_{message_id}.jpg"
                else:
                    file_name = f"{message_id}.jpg"
                
                uploaded_file_id = upload_image_to_drive(image_data, file_name)
                if uploaded_file_id:
                    print(f"圖片已上傳到 Google Drive: {uploaded_file_id}")
                else:
                    print("圖片上傳失敗")
            
            return "OK"
        return "No Event", 200
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return "Internal Server Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
