from flask import Flask, request, jsonify
import json
import gspread
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import io
import datetime
import pytz
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

app = Flask(__name__)

# LINE Bot API 設定
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
SPREADSHEET_NAME = "LineMessages"
LINE_ID_SPREADSHEET_ID = "1uuIEQdD_maLJFG3Qj-gIPWw0w5Ph0leRyrOed_LNmOM"
MAIL_SPREADSHEET_ID = "13E14q3yzwgnc__vD2hZKYduIwHxGDQabU_VyrtSR8i4"

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
mail_sheet = gc.open_by_key(MAIL_SPREADSHEET_ID).sheet1

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

@app.route("/send", methods=["GET"])
def send_messages():
    try:
        # 固定的班級與作文標題
        std_class = "線中六"
        title = "一趟豐富之旅"

        # 文字訊息
        text_message = TextSendMessage(text="【作文評語】\n親愛的家長，您好！附檔為芷瑢老師批閱後的作文評語（也有同步mail回信給孩子），還請孩子詳細看過並了解問題點，老師上課會進行總檢討，也同時讓家長掌握孩子的學習成果，謝謝您！")

        # 讀取 Google Sheets 資料
        records = mail_sheet.get_all_records()

        for row in records:
            send_image = str(row.get('hw', '')).strip().lower() == 'y'
            send_text = str(row.get('txt', '')).strip().lower() == 'y'

            id_field = str(row.get('id', '')).strip()
            if ',' in id_field:
                user_ids = [uid.strip() for uid in id_field.split(',')]
            else:
                user_ids = [id_field] if id_field else []

            name = str(row.get('name', '')).strip()

            if user_ids and name:
                encoded_name = urllib.parse.quote(name)
                encoded_class = urllib.parse.quote(std_class)
                encoded_title = urllib.parse.quote(title)

                image_url = f"https://hsinhua.net/composition/{encoded_class}/{encoded_title}/orig/{encoded_name}.jpg"
                image_url_pre = f"https://hsinhua.net/composition/{encoded_class}/{encoded_title}/pre/{encoded_name}.jpg"
                image_message = ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url_pre
                )

                for user_id in user_ids:
                    user_id = user_id.strip()
                    if user_id:
                        messages = []
                        if send_text:
                            messages.append(text_message)
                        if send_image:
                            messages.append(image_message)

                        if messages:
                            try:
                                line_bot_api.push_message(user_id, messages)
                            except Exception as e:
                                print(f"發送訊息給 {user_id} 失敗: {e}")

        return "Messages sent successfully!", 200
    except Exception as e:
        print(f"發生錯誤: {e}")
        return "Error", 500
        
@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature")

    try:
        json_data = json.loads(body)
        print(f"收到的 JSON: {json.dumps(json_data, indent=2)}")  # Debugging

        if "events" in json_data:
            for event in json_data["events"]:  # 遍歷所有事件
                print(f"處理事件: {event}")  # Debugging

                user_id = event["source"]["userId"]
                message_type = event["message"].get("type", "")
                message_id = event["message"].get("id", "")

                # 獲取台灣時間
                taiwan_tz = pytz.timezone("Asia/Taipei")
                taiwan_time = datetime.datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S")

                # 處理文字訊息
                if message_type == "text":
                    message_text = event["message"].get("text", "")
                    print(f"收到文字訊息: {message_text}")  # Debugging

                    try:
                        sheet.append_row([taiwan_time, user_id, message_text])
                        print("成功寫入 Google Sheet")
                    except Exception as sheet_error:
                        print(f"寫入 Google Sheet 失敗: {sheet_error}")

                # 處理圖片訊息
                elif message_type == "image":
                    print(f"收到圖片訊息: {message_id}")  # Debugging
                    sheet.append_row([taiwan_time, user_id, f"Image ID: {message_id}"])

                    # 獲取 class 和 std
                    class_name, std_name = get_class_std_from_user_id(user_id)
                    file_name = f"{class_name}_{std_name}_{message_id}.jpg" if class_name and std_name else f"{message_id}.jpg"

                    # 下載圖片內容
                    message_content = line_bot_api.get_message_content(message_id)
                    image_data = io.BytesIO(message_content.content)

                    # 上傳圖片到 Google Drive
                    uploaded_file_id = upload_image_to_drive(image_data, file_name)
                    if uploaded_file_id:
                        print(f"圖片已上傳到 Google Drive: {uploaded_file_id}")
                    else:
                        print("圖片上傳失敗")

            return "OK"
        else:
            print("沒有事件需要處理")
            return "No Event", 200

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return "Internal Server Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
