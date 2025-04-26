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
import urllib.parse
import time
import yagmail
from google.auth.exceptions import TransportError
import time

'''
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
'''
# Line 群發注意事項：

# 第 260 行左右
# 注意！要先定義班級 std_class 和作文主題 title
# 注意！要先定義班級 std_class 和作文主題 title
# 注意！要先定義班級 std_class 和作文主題 title

# 注意！圖檔要上傳到網站
# 注意！圖檔要上傳到網站
# 注意！圖檔要上傳到網站

# 第 55 行左右
# MAIL_SPREADSHEET_ID 需先用測試
# MAIL_SPREADSHEET_ID 需先用測試
# MAIL_SPREADSHEET_ID 需先用測試

app = Flask(__name__)

# LINE Bot API 設定
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# Google Sheets API 和 Google Drive API 的憑證檔案
SHEET_CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
MSG_SPREADSHEET_ID = "1p6K5yoQLMnAoS5eLRGEYUVcuI6pIzifmg7VunZHUWR0"
LINE_ID_SPREADSHEET_ID = "1uuIEQdD_maLJFG3Qj-gIPWw0w5Ph0leRyrOed_LNmOM"
#正式
#MAIL_SPREADSHEET_ID = "1w5brdzpIELPZaKa8C_QGcRK1byZLXXQwBz1FM0rsqVA"
#測試
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
sheet = gc.open_by_key(MSG_SPREADSHEET_ID).sheet1
line_id_sheet = gc.open_by_key(LINE_ID_SPREADSHEET_ID).sheet1
mail_sheet = gc.open_by_key(MAIL_SPREADSHEET_ID).sheet1

# Google Drive API 的資料夾ID
FOLDER_ID = '11f2Z7Js8uBYWR-h4UUfbBPDZNKzx9qYO'

def safe_get_records(sheet, retries=5):
    """安全地讀取 Google Sheets 資料，最多重試 5 次"""
    for attempt in range(retries):
        try:
            return sheet.get_all_records()
        except TransportError as e:
            print(f"Google Sheets API 讀取失敗 (TransportError)，重試 {attempt+1}/{retries} 次...: {e}")
            time.sleep(2**attempt)  # 2 的指數次回退
        except Exception as e:
            print(f"Google Sheets API 讀取失敗，重試 {attempt+1}/{retries} 次...: {e}")
            time.sleep(2**attempt)
    print("Google Sheets API 讀取失敗，請確認 API 設定或網路狀況")
    return []
    
def send_email(subject):
    """ 使用 Google OAuth2 發送郵件，確保憑證有效 """
    GCP_CREDENTIALS = os.getenv("GCP_CREDENTIALS")

    if not GCP_CREDENTIALS:
        raise ValueError("GCP_CREDENTIALS 環境變數未設定")
    
    try:
        credentials_dict = json.loads(GCP_CREDENTIALS)
    except json.JSONDecodeError:
        raise ValueError("GCP_CREDENTIALS 格式錯誤，請檢查環境變數")

    EMAIL_ADDRESS = credentials_dict.get("email_address")
    if not EMAIL_ADDRESS:
        raise ValueError("Google 憑證缺少 `email_address` 欄位")

    TEMP_CREDENTIALS_FILE = "/tmp/gcp_credentials.json"
    with open(TEMP_CREDENTIALS_FILE, "w") as f:
        json.dump(credentials_dict, f)

    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, oauth2_file=TEMP_CREDENTIALS_FILE)
    except Exception as e:
        print(f"無法初始化 Yagmail，請確認 OAuth2 設定: {e}")
        return

    for attempt in range(3):
        try:
            yag.send(
                to=EMAIL_ADDRESS,  
                subject=subject or "No Subject",  
                contents="This is a test email."
            )
            print("郵件已成功發送！")
            return
        except Exception as e:
            print(f"發送郵件失敗 (嘗試 {attempt+1}/3): {e}")
            time.sleep(2**attempt)  # 2 的指數次退避
    print("郵件最終仍然發送失敗")

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
'''
def is_new_user(user_id):
    """檢查 user_id 是否存在於 Google Sheets"""
    records = safe_get_records(line_id_sheet)  # 改用 safe_get_records()
    return not any(record.get("id") == user_id for record in records)
# 定義自動重試機制
'''
def is_new_user(user_id):
    """從第 1 欄抓取所有 userId，效能高且不易 timeout"""
    for attempt in range(3):
        try:
            id_list = line_id_sheet.col_values(1)  # 假設 id 欄在第 1 欄
            return user_id not in id_list
        except Exception as e:
            print(f"檢查是否為新使用者失敗，第 {attempt+1} 次重試: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    print("多次嘗試後仍無法存取 Google Sheets")
    return False  # 為保險起見，失敗時視為舊使用者，避免 crash
'''
def get_user_name(user_id):
    """從 LINE_ID_SPREADSHEET_ID 取得 user_name"""
    records = safe_get_records(line_id_sheet)  # 安全地讀取試算表
    for record in records:
        if record.get("id") == user_id:  # 確保 `id` 欄位匹配
            return record.get("name", "Unknown")  # 預設為 "Unknown" 以防沒有名稱
    return "Unknown"
'''
def get_user_name(user_id):
    """從 Google Sheets 中根據 user_id 取得對應的名稱，效能優化版"""
    for attempt in range(3):
        try:
            all_values = line_id_sheet.get_all_values()  # 不轉 dict，比 get_all_records 快
            for row in all_values:
                if len(row) >= 2 and row[0] == user_id:  # 確保有足夠欄位
                    return row[3]  # 假設第 2 欄是 name
            return "Unknown"
        except Exception as e:
            print(f"取得 user name 失敗，第 {attempt+1} 次重試: {e}")
            time.sleep(2 ** attempt)
    return "Unknown"

def retry_function(func, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            print(f"發生錯誤: {e}，重試 {attempt + 1}/{retries}...")
            time.sleep(delay)
    print("多次重試仍然失敗")
    return "Internal Server Error", 500

def expand_sheet_if_needed(sheet, extra_rows=100):
    """
    如果 Google Sheets 行數不足，則擴展行數 (一次增加 extra_rows)
    """
    try:
        # 取得目前的行數
        current_rows = len(sheet.get_all_values())

        # 取得 Google Sheets 允許的最大行數 (通常是 10,000，但可以手動擴展)
        max_rows = sheet.row_count  # 這是 Google Sheets 目前的最大行數限制

        if current_rows >= max_rows:
            # 增加 `extra_rows`，避免超出 Google Sheets 限制
            new_max_rows = max_rows + extra_rows
            sheet.add_rows(extra_rows)
            print(f"擴展 Google Sheets 行數到 {new_max_rows}")

    except Exception as e:
        print(f"擴展 Google Sheets 失敗: {e}")

def safe_append_row(sheet, row, retries=5):
    """安全地寫入 Google Sheets，最多重試 5 次"""
    for attempt in range(retries):
        try:
            sheet.append_row(row)
            print("成功寫入 Google Sheet")
            return True
        except TransportError as e:
            print(f"Google Sheets API 連線錯誤 (TransportError)，重試 {attempt+1}/{retries} 次...: {e}")
        except Exception as e:
            print(f"寫入 Google Sheets 失敗，重試 {attempt+1}/{retries} 次...: {e}")
        time.sleep(2**attempt)  # 2 的指數次回退
    print("寫入 Google Sheets 失敗，請確認 API 設定或網路狀況")
    return False  # 最終還是失敗
    
@app.route("/", methods=["GET"])
def keep_alive():
    return "OK", 200

@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200
    
@app.route("/send", methods=["GET"])
def send_messages():
    try:
        # 固定的班級與作文標題
        std_class = "線高三"
        title = "未成功的物品展覽會"

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

                image_url = f"https://bizbear.cc/composition/{encoded_class}/{encoded_title}/orig/{encoded_name}.jpg"
                image_url_pre = f"https://bizbear.cc/composition/{encoded_class}/{encoded_title}/pre/{encoded_name}.jpg"
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

    def process_request():
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

                    # 檢查是否為新使用者
                    new_user_flag = "new" if is_new_user(user_id) else ""
                    
                    # 獲取 user_name
                    user_name = get_user_name(user_id)

                    # 處理文字訊息
                    if message_type == "text":
                        message_text = event["message"].get("text", "")
                        print(f"收到文字訊息: {message_text}")  # Debugging

                        try:
                            # 存入 Google Sheet（包含 user_name）
                            safe_append_row(sheet, [taiwan_time, user_id, user_name, message_text, new_user_flag])
                            print("文字訊息成功寫入 Google Sheet")
                        except Exception as sheet_error:
                            print(f"寫入 Google Sheet 失敗: {sheet_error}")

                    # 處理圖片訊息
                    elif message_type == "image":
                        print(f"收到圖片訊息: {message_id}")  # Debugging

                        try:
                            safe_append_row(sheet, [taiwan_time, user_id, user_name, f"image id: {message_id}", new_user_flag])
                            print("圖片訊息成功寫入 Google Sheet")
                        except Exception as sheet_error:
                            print(f"寫入 Google Sheet 失敗: {sheet_error}")

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
                            send_email(file_name)
                        else:
                            print("圖片上傳失敗")

                        # 檢查檔名是否包含「女」
                        #if "女" in file_name:
                        #    send_email(file_name, "")  # 發送郵件

                    # 處理貼圖訊息
                    elif message_type == "sticker":
                        sticker_id = event["message"].get("stickerId", "")
                        print(f"收到貼圖訊息: Sticker ID {sticker_id}")  # Debugging

                        try:
                            safe_append_row(sheet, [taiwan_time, user_id, user_name, f"sticker id: {sticker_id}", new_user_flag])
                            print("貼圖訊息成功寫入 Google Sheet")
                        except Exception as sheet_error:
                            print(f"寫入 Google Sheet 失敗: {sheet_error}")

                return "OK"
            else:
                print("沒有事件需要處理")
                return "No Event", 200
        except Exception as e:
            print(f"發生未預期的錯誤: {e}")
            raise e  # 讓 retry_function 捕捉錯誤並重試
    
    return retry_function(process_request)

@app.route("/lecture", methods=["GET"])
def send_lecture_links():
    try:
        # 開啟目標試算表
        lecture_sheet = gc.open_by_key("14TwhcFFfW3B4323jWcdAIaOoGey6Qk8p2pdw0j0-UwE").sheet1
        rows = lecture_sheet.get_all_values()

        for row in rows:
            if len(row) >= 8:
                user_id = row[0].strip()
                class_info = row[1].strip()
                code = row[7].strip()

                if "線上" in class_info and user_id and code:
                    message = TextSendMessage(
                        text=(
                            "【請填寫講義領取方式】\n"
                            "親愛的家長，您好！請進入以下網站來填寫講義領取方式，確認無誤後，請按「確認送出」，謝謝您！\n"
                            f"https://bizbear.cc/address-form.php?code={code}"
                        )
                    )
                    try:
                        line_bot_api.push_message(user_id, message)
                        print(f"已發送訊息給 {user_id}")
                    except Exception as e:
                        print(f"發送訊息給 {user_id} 失敗: {e}")

        return "Lecture links sent!", 200
    except Exception as e:
        print(f"/lecture 發生錯誤: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
