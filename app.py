from flask import Flask, request, jsonify
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = Flask(__name__)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
DRIVE_CREDENTIALS_FILE = "newagent-gfvg-8e261d5a3c37.json"
SPREADSHEET_NAME = "LineMessages"  # 試算表名稱（請確保你已創建該試算表）

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
            message_text = event["message"]["text"]
            
            # 將 user_id 和訊息寫入 Google 試算表
            sheet.append_row([user_id, message_text])

            print(f"接收到事件: {event}")
            return "OK"
        else:
            print("沒有事件需要處理")
            return "No Event", 200

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return "Internal Server Error", 500

@app.route('/upload', methods=['POST'])
def upload_image():
    """處理圖片上傳並儲存到 Google Drive 資料夾"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 儲存圖片到本地暫存
    file_path = os.path.join('/tmp', file.filename)
    file.save(file_path)

    # 上傳檔案到 Google Drive
    try:
        service = get_drive_service()
        
        # 創建 Google Drive 檔案元數據
        file_metadata = {
            'name': file.filename,
            'parents': [FOLDER_ID]
        }

        media = MediaFileUpload(file_path, mimetype='image/jpeg')

        # 上傳檔案
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        # 刪除本地暫存檔案
        os.remove(file_path)

        return jsonify({"message": "File uploaded successfully", "file_id": uploaded_file['id']}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
