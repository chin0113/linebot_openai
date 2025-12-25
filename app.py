from flask import Flask, request, jsonify
from flask_cors import CORS
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
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
socket.setdefaulttimeout(20)  # 20 秒還拿不到回應就丟 timeout
import uuid

# 建一個有重試的 Session（全域共用）
session = requests.Session()
retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)

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
CORS(app)

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
        
def upload_file_to_drive(file_bytes, file_name, mimetype='application/octet-stream'):
    """
    將任意檔案上傳到與圖片相同的資料夾（FOLDER_ID）。
    file_bytes: BytesIO
    file_name: 檔名（含副檔名）
    mimetype: 例如 'application/pdf'
    """
    try:
        service = get_drive_service()            # 這裡改用同一個取 service 的方法
        file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
        if hasattr(file_bytes, "seek"):
            file_bytes.seek(0)
        media = MediaIoBaseUpload(file_bytes, mimetype=mimetype)
        uploaded = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        return uploaded.get('id')
    except Exception as e:
        print(f"檔案上傳失敗: {e}")
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

def check_image_exists(url: str) -> bool:
    """
    穩健版圖片存在檢查：
    1) 先 HEAD（快），允許 redirect；接受 200/301/302。
    2) 再用 Range: bytes=0-0 的極小 GET（相容性高）；接受 200/206。
    超時策略：HEAD 稍短、GET 稍長，降低偽陰性。
    """
    # 優先用 HEAD，減少下載等待
    try:
        r = session.head(url, allow_redirects=True, timeout=(1.2, 1.8))
        if r.status_code in (200, 301, 302):
            return True
    except requests.RequestException as e:
        print(f"[image-check HEAD] {url} -> {e}")

    # 若 HEAD 不可靠/不支援，退回極小範圍 GET
    try:
        r = session.get(
            url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            allow_redirects=True,
            timeout=(1.5, 2.5),
        )
        if r.status_code in (200, 206):
            return True
    except requests.RequestException as e:
        print(f"[image-check GET-range] {url} -> {e}")

    return False
    
TW_TZ = pytz.timezone("Asia/Taipei")

def now_tw_str():
    return datetime.datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")

def extract_event_info(event: dict) -> dict:
    msg = event.get("message", {}) or {}
    src = event.get("source", {}) or {}
    delivery = event.get("deliveryContext", {}) or {}

    info = {
        "tw_time": now_tw_str(),  # 你 server 接到的台灣時間
        "timestamp_ms": event.get("timestamp"),  # LINE event timestamp (ms)
        "webhookEventId": event.get("webhookEventId"),
        "isRedelivery": delivery.get("isRedelivery"),
        "mode": event.get("mode"),
        "source_type": src.get("type"),
        "userId": src.get("userId"),             # ✅ 你要的 LINE userId
        "groupId": src.get("groupId"),
        "roomId": src.get("roomId"),
        "event_type": event.get("type"),
        "message_type": msg.get("type"),
        "message_id": msg.get("id"),
    }

    # 文字內容（注意：可能含個資，若你不想記錄可註解）
    if msg.get("type") == "text":
        info["text"] = msg.get("text", "")

    # 圖片多張（imageSet）
    if msg.get("type") == "image":
        image_set = msg.get("imageSet")
        if image_set:
            info["imageSetId"] = image_set.get("id")
            info["imageIndex"] = image_set.get("index")
            info["imageTotal"] = image_set.get("total")

    # 檔案
    if msg.get("type") == "file":
        info["fileName"] = msg.get("fileName")
        info["fileSize"] = msg.get("fileSize")

    # 貼圖
    if msg.get("type") == "sticker":
        info["stickerId"] = msg.get("stickerId")
        info["packageId"] = msg.get("packageId")

    return info

def log_event(tag: str, request_id: str, info: dict, extra: dict | None = None):
    payload = {
        "tag": tag,
        "request_id": request_id,
        **info,
    }
    if extra:
        payload.update(extra)
    # 一行 JSON：最適合 Render log 搜尋與比對
    print(json.dumps(payload, ensure_ascii=False))

@app.route("/", methods=["GET"])
def keep_alive():
    return "OK", 200

@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200
    
from flask import request

@app.route("/send", methods=["POST"])
def send_messages():
    try:
        data = request.get_json()
        std_class = data.get("std_class", "").strip()
        title = data.get("title", "").strip()

        if not std_class or not title:
            return jsonify({"error": "std_class 和 title 都必須提供"}), 400

        print(f"\n即將傳送給班級：{std_class}，主題：{title}")

        text_message = TextSendMessage(
            text="【作文評語】\n親愛的家長，您好！附檔為芷瑢老師批閱後的作文評語（也有同步mail回信給孩子），還請孩子詳細看過並了解問題點，老師上課會進行總檢討，也同時讓家長掌握孩子的學習成果，謝謝您！"
        )

        records = mail_sheet.get_all_records()

        for row in records:
            class_name = str(row.get('class', '')).strip()
            if class_name != std_class:
                continue

            send_image = str(row.get('hw', '')).strip().lower() == 'y'
            send_text  = str(row.get('txt', '')).strip().lower() == 'y'
            if not (send_image or send_text):
                continue

            id_field = str(row.get('id', '')).strip()
            user_ids = [uid.strip() for uid in id_field.split(',')] if ',' in id_field else ([id_field] if id_field else [])
            name = str(row.get('name', '')).strip()
            if not (user_ids and name):
                continue

            enc_name  = urllib.parse.quote(name)
            enc_class = urllib.parse.quote(std_class)
            enc_title = urllib.parse.quote(title)

            image_url     = f"https://bizbear.cc/composition/{enc_class}/{enc_title}/orig/{enc_name}.jpg"
            image_url_pre = f"https://bizbear.cc/composition/{enc_class}/{enc_title}/pre/{enc_name}.jpg"

            # ---- 關鍵：若「需要圖片」，圖片不可用 → 直接略過此學生（文字也不送） ----
            if send_image:
                image_ok = check_image_exists(image_url)
                if not image_ok:
                    print(f"[skip student] 圖片不可用 → 略過 {name}（文字與圖片皆不送）: {image_url}")
                    continue

            # 構造訊息（若 send_image==True，到這裡一定 image_ok==True）
            image_message = None
            if send_image:
                image_message = ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url_pre
                )

            for user_id in user_ids:
                if not user_id:
                    continue
                messages = []
                # 若不需要圖片、但要文字 → 只送文字
                if send_text and (not send_image):
                    messages.append(text_message)
                # 若需要圖片（且已確認可用）→ 根據 send_text/sen_image 組裝
                if send_image:
                    if send_text:
                        messages.append(text_message)
                    messages.append(image_message)

                if not messages:
                    continue

                try:
                    line_bot_api.push_message(user_id, messages)
                    time.sleep(0.05)  # 略降等待，減少整體阻塞時間
                except Exception as e:
                    print(f"發送訊息給 {user_id} 失敗: {e}")

        return jsonify({"message": "Messages sent successfully!"}), 200

    except Exception as e:
        print(f"發生錯誤: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/notify", methods=["POST"])
def notify_messages():
    try:
        data = request.get_json()
        image_names_raw = data.get("image_names", "").strip()
        #message_text = data.get("message_text", "").strip()
        message_texts = [t.strip() for t in data.get("message_texts", []) if t.strip()]
        order = data.get("order", "text-first")

        send_text = bool(message_texts)
        send_image = bool(image_names_raw)

        if not send_text and not send_image:
            return jsonify({"error": "請至少提供圖片名稱或文字訊息"}), 400

        #image_names = [name.strip() for name in image_names_raw.split(',') if name.strip()] if send_image else []
        image_names = [urllib.parse.unquote(name.strip()) for name in image_names_raw.split(',') if name.strip()] if send_image else []

        #text_message = TextSendMessage(text=message_text) if send_text else None
        text_messages = [TextSendMessage(text=t) for t in message_texts]

        # ✅ 圖片存在性檢查（統一一次性驗證）
        if send_image:
            for img_name in image_names:
                encoded_img_name = urllib.parse.quote(img_name)
                image_url = f"https://bizbear.cc/composition/notify/orig/{encoded_img_name}"
                for i in range(2):
                    try:
                        response = requests.head(image_url, timeout=3)
                        if response.status_code == 200:
                            break
                    except Exception as e:
                        print(f"檢查圖片失敗 {i+1} 次：{e}")
                    if i == 1:
                        print(f"❌ 終止：圖片不存在 - {image_url}")
                        return jsonify({"error": f"圖片不存在：{img_name}"}), 400
                    time.sleep(1)

        # ✅ 確保圖片都存在後，才發送訊息
        records = mail_sheet.get_all_records()
        for row in records:
            if str(row.get('hw', '')).strip().lower() != 'y':
                continue

            id_field = str(row.get('id', '')).strip()
            if ',' in id_field:
                user_ids = [uid.strip() for uid in id_field.split(',')]
            else:
                user_ids = [id_field] if id_field else []

            image_messages = []
            if send_image:
                for img_name in image_names:
                    encoded_img_name = urllib.parse.quote(img_name)
                    image_url = f"https://bizbear.cc/composition/notify/orig/{encoded_img_name}"
                    image_url_pre = f"https://bizbear.cc/composition/notify/pre/{encoded_img_name}"
                    image_messages.append(ImageSendMessage(
                        original_content_url=image_url,
                        preview_image_url=image_url_pre
                    ))

            for user_id in user_ids:
                user_id = user_id.strip()
                if user_id:
                    messages = []
                    if order == "text-first":
                        messages.extend(text_messages)     # 多段文字
                        messages.extend(image_messages)
                    else:
                        messages.extend(image_messages)
                        messages.extend(text_messages)     # 多段文字

                    if messages:
                        try:
                            line_bot_api.push_message(user_id, messages)
                        except Exception as e:
                            print(f"發送給 {user_id} 失敗：{e}")

        return jsonify({"message": "Notify messages sent!"}), 200

    except Exception as e:
        print(f"❌ notify 發生錯誤：{e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)
    request_id = uuid.uuid4().hex[:8]  # 短 id 好看

    try:
        json_data = json.loads(body)
        events = json_data.get("events", []) or []

        print(json.dumps({
            "tag": "webhook_received",
            "request_id": request_id,
            "tw_time": now_tw_str(),
            "events_count": len(events)
        }, ensure_ascii=False))

        for event in events:
            info = extract_event_info(event)
            log_event("event_start", request_id, info)

            try:
                # ✅ 你原本處理 event 的程式碼放這裡
                user_id = event["source"]["userId"]
                message_type = event["message"].get("type", "")
                message_id = event["message"].get("id", "")

                taiwan_tz = pytz.timezone("Asia/Taipei")
                taiwan_time = datetime.datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S")

                new_user_flag = "new" if is_new_user(user_id) else ""
                user_name = get_user_name(user_id)

                if message_type == "text":
                    message_text = event["message"].get("text", "")
                    safe_append_row(sheet, [taiwan_time, user_id, user_name, message_text, new_user_flag])

                elif message_type == "image":
                    safe_append_row(sheet, [taiwan_time, user_id, user_name, f"image id: {message_id}", new_user_flag])

                    class_name, std_name = get_class_std_from_user_id(user_id)
                    file_name = f"{class_name}_{std_name}_{message_id}.jpg" if class_name and std_name else f"{message_id}.jpg"

                    message_content = line_bot_api.get_message_content(message_id)
                    image_data = io.BytesIO(message_content.content)

                    uploaded_file_id = upload_image_to_drive(image_data, file_name)
                    if uploaded_file_id:
                        print(f"圖片已上傳到 Google Drive: {uploaded_file_id}")

                elif message_type == "sticker":
                    sticker_id = event["message"].get("stickerId", "")
                    safe_append_row(sheet, [taiwan_time, user_id, user_name, f"sticker id: {sticker_id}", new_user_flag])

                elif message_type == "file":
                    file_name = event["message"].get("fileName", "")
                    if file_name and file_name.lower().endswith(".pdf"):
                        safe_append_row(sheet, [taiwan_time, user_id, user_name, f"pdf: {file_name}", new_user_flag])

                        message_content = line_bot_api.get_message_content(message_id)
                        pdf_bytes = io.BytesIO(message_content.content)

                        class_name, std_name = get_class_std_from_user_id(user_id)
                        save_name = f"{class_name}_{std_name}_{file_name}" if class_name and std_name else file_name

                        uploaded_pdf_id = upload_file_to_drive(pdf_bytes, save_name, mimetype='application/pdf')
                        if uploaded_pdf_id:
                            print(f"PDF 已上傳到 Google Drive: {uploaded_pdf_id}")
                            
                log_event("event_ok", request_id, info)

            except Exception as e:
                log_event("event_error", request_id, info, {"error": str(e)})
                continue

        print(json.dumps({
            "tag": "webhook_done",
            "request_id": request_id,
            "tw_time": now_tw_str()
        }, ensure_ascii=False))
        return "OK", 200

    except Exception as e:
        print(json.dumps({
            "tag": "webhook_parse_error",
            "request_id": request_id,
            "tw_time": now_tw_str(),
            "error": str(e)
        }, ensure_ascii=False))
        return "OK", 200

@app.route("/lecture", methods=["GET"])
def send_lecture_links():
    try:
        # 開啟目標試算表
        lecture_sheet = gc.open_by_key("14TwhcFFfW3B4323jWcdAIaOoGey6Qk8p2pdw0j0-UwE").sheet1
        rows = lecture_sheet.get_all_values()

        for row in rows:
            if len(row) >= 9:
                user_id = row[0].strip()
                class_info = row[1].strip()
                code = row[7].strip()
                send_flag = row[8].strip().lower()

                if "線上" in class_info and user_id and code and send_flag == "y":
                    # 第一段訊息
                    message1 = TextSendMessage(
                        text=(
                            "【請提供講義收件地址】\n"
                            "親愛的家長，您好！為郵寄春夏班線上課程講義，我們將以 「掛號」 形式寄出（預計2月第一週寄出，寄出後會訊息通知），收件者為學生姓名，麻煩點選以下連結填寫地址，謝謝您。～行政組～"
                        )
                    )

                    # 第二段訊息
                    message2 = TextSendMessage(
                        text=(
                            "確認無誤後，請按「確認送出」：\n\n"
                            f"https://bizbear.cc/address-form.php?code={code}"
                        )
                    )

                    try:
                        line_bot_api.push_message(user_id, [message1, message2])
                        print(f"✅ 已發送訊息給 {user_id}")
                    except Exception as e:
                        print(f"❌ 發送訊息給 {user_id} 失敗: {e}")

        return "Lecture links sent!", 200
    except Exception as e:
        print(f"/lecture 發生錯誤: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
