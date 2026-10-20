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
import secrets
import re
import hashlib
import hmac
import unicodedata

from queue import Queue
import threading
import tempfile

EVENT_Q = Queue(maxsize=1000)
SHEET_LOCK = threading.Lock()

# =========================
# (A) 新增：送訊息背景工作佇列（給 /send 用）
# =========================
JOB_Q = Queue(maxsize=200)
JOBS = {}
JOBS_LOCK = threading.Lock()

_JOB_WORKER_STARTED = False
JOBS_TTL_SEC = 6 * 3600  # 只保留 6 小時內的 job，避免記憶體一直長

def _gc_jobs(now_ts: float):
    # 清掉過期 job
    expired = []
    for jid, info in JOBS.items():
        ts = info.get("_ts")
        if ts and (now_ts - ts) > JOBS_TTL_SEC:
            expired.append(jid)
    for jid in expired:
        JOBS.pop(jid, None)

def set_job(job_id: str, **kwargs):
    now_ts = time.time()
    with JOBS_LOCK:
        _gc_jobs(now_ts)
        prev = JOBS.get(job_id, {})
        JOBS[job_id] = {
            **prev,
            **kwargs,
            "updated_at": now_tw_str(),
            "_ts": prev.get("_ts", now_ts),  # job 建立時間（for TTL）
        }

def job_worker():
    while True:
        job = JOB_Q.get()
        job_id = job["job_id"]
        try:
            set_job(job_id, status="running", started_at=now_tw_str())

            if job["type"] == "send":
                _do_send(job["std_class"], job["title"], job_id)
            elif job["type"] == "lecture":
                _do_lecture(job["payload"], job_id)
            elif job["type"] == "notify":
                _do_notify(job["payload"], job_id)  # 你未來若要把 /notify 也改背景再用

            set_job(job_id, status="done", finished_at=now_tw_str())
        except Exception as e:
            set_job(job_id, status="error", error=str(e), finished_at=now_tw_str())
        finally:
            JOB_Q.task_done()

def ensure_job_worker_started():
    global _JOB_WORKER_STARTED
    if _JOB_WORKER_STARTED:
        return
    t = threading.Thread(target=job_worker, daemon=True)
    t.start()
    _JOB_WORKER_STARTED = True
    print("[job_worker] started")

# ==========================================================
# Cloudflare R2 作文圖片來源切換（只影響 /send，不影響 /notify）
# COMPOSITION_IMAGE_PROVIDER 預設 knownhost，測試成功再於 Render 設成 r2。
# R2_PATH_SECRET 請設於 Render 的 Environment，必須與本機上傳程式相同。
# ==========================================================
COMPOSITION_IMAGE_PROVIDER = os.getenv("COMPOSITION_IMAGE_PROVIDER", "knownhost").strip().lower()
R2_PATH_SECRET = os.getenv("R2_PATH_SECRET", "")
R2_IMAGE_BASE_URL = "https://iread327-images.iread327.workers.dev"

# 通知圖片來源開關：預設保持舊主機，完成 R2 實測後再設 r2
NOTIFY_IMAGE_PROVIDER = os.getenv("NOTIFY_IMAGE_PROVIDER", "knownhost").strip().lower()


def r2_private_token(*parts):
    """完全對齊 PDF轉JPG_R2完整上傳.py 的 private_token()。"""
    if len(R2_PATH_SECRET.encode("utf-8")) < 32:
        raise RuntimeError("R2_PATH_SECRET 尚未於 Render 環境變數設定（至少 32 bytes）。")
    content = "\x00".join(
        unicodedata.normalize("NFC", str(part).strip()) for part in parts
    ).encode("utf-8")
    return hmac.new(
        R2_PATH_SECRET.encode("utf-8"), content, hashlib.sha256
    ).hexdigest()[:32]


def composition_image_urls(std_class, title, name):
    """回傳 (orig_url, pre_url)；切換來源但保留發送順序及訊息邏輯。"""
    if COMPOSITION_IMAGE_PROVIDER == "r2":
        batch_id = r2_private_token("batch", std_class, title)
        student_id = r2_private_token("student", std_class, title, name)
        root = f"{R2_IMAGE_BASE_URL}/composition/v1/{batch_id}"
        return (
            f"{root}/orig/{student_id}.jpg",
            f"{root}/pre/{student_id}.jpg",
        )

    if COMPOSITION_IMAGE_PROVIDER == "knownhost":
        enc_class = urllib.parse.quote(std_class)
        enc_title = urllib.parse.quote(title)
        enc_name = urllib.parse.quote(name)
        return (
            f"https://bizbear.cc/composition/{enc_class}/{enc_title}/orig/{enc_name}.jpg",
            f"https://bizbear.cc/composition/{enc_class}/{enc_title}/pre/{enc_name}.jpg",
        )

    raise RuntimeError(
        "COMPOSITION_IMAGE_PROVIDER 僅接受 knownhost 或 r2。"
    )


def notify_image_urls(image_name: str):
    """沿用 /notify 的圖片名稱輸入方式，僅切換原圖與縮圖來源。"""
    if NOTIFY_IMAGE_PROVIDER == "knownhost":
        encoded_name = urllib.parse.quote(image_name)
        return (
            f"https://bizbear.cc/composition/notify/orig/{encoded_name}",
            f"https://bizbear.cc/composition/notify/pre/{encoded_name}",
        )

    if NOTIFY_IMAGE_PROVIDER == "r2":
        # 與 Windows notify_R2_upload.py 完全相同的 HMAC 規則。
        # 使用原始完整檔名（含副檔名）計算，避免不同格式相互覆蓋。
        file_name = unicodedata.normalize("NFC", image_name.strip())
        if not file_name or "/" in file_name or "\\" in file_name or "\x00" in file_name:
            raise ValueError("R2 通知圖片名稱不可包含路徑分隔字元")
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            raise ValueError("R2 通知圖片只支援 JPG、JPEG、PNG")
        image_id = r2_private_token("notify", file_name)
        base = f"{R2_IMAGE_BASE_URL}/composition/notify/v1/{image_id}"
        return f"{base}/orig{ext}", f"{base}/pre{ext}"

    raise RuntimeError("NOTIFY_IMAGE_PROVIDER 僅接受 knownhost 或 r2")


# =========================
# (B) /send 的重活搬到這裡跑（背景 worker 執行）
# =========================
def _do_send(std_class: str, title: str, job_id: str):
    set_job(job_id, progress="loading_sheet", std_class=std_class, title=title)

    print(f"\n[job:{job_id}] 即將傳送給班級：{std_class}，主題：{title}")

    text_message = TextSendMessage(
        text="【作文評語】\n親愛的家長，您好！附檔為芷瑢老師批閱後的作文評語（也有同步mail回信給孩子），還請孩子詳細看過並了解問題點，老師上課會進行總檢討，也同時讓家長掌握孩子的學習成果，謝謝您！"
    )

    # 讀 sheet（加鎖：你程式本來就有 SHEET_LOCK）
    with SHEET_LOCK:
        records = mail_sheet.get_all_records()

    scanned = 0
    matched = 0
    sent_ok = 0
    sent_fail = 0
    skipped = 0

    for row in records:
        scanned += 1

        class_name = str(row.get('class', '')).strip()
        if class_name != std_class:
            continue
        matched += 1

        send_image = str(row.get('hw', '')).strip().lower() == 'y'
        send_text  = str(row.get('txt', '')).strip().lower() == 'y'
        if not (send_image or send_text):
            skipped += 1
            continue

        id_field = str(row.get('id', '')).strip()
        user_ids = [uid.strip() for uid in id_field.split(',')] if ',' in id_field else ([id_field] if id_field else [])
        name = str(row.get('name', '')).strip()
        if not (user_ids and name):
            skipped += 1
            continue

        # 其他 LINE 發送邏輯維持不變；只切換兩張圖片的來源 URL。
        image_url, image_url_pre = composition_image_urls(std_class, title, name)

        # 需要圖片但圖片不可用 → 略過此學生（文字也不送）
        if send_image:
            image_ok = check_image_exists(image_url)
            if not image_ok:
                print(f"[job:{job_id}] [skip student] 圖片不可用 → 略過 {name}: {image_url}")
                skipped += 1
                # 每 20 筆更新一次 job（避免 log/lock 太頻繁）
                if (sent_ok + sent_fail + skipped) % 20 == 0:
                    set_job(job_id, scanned=scanned, matched=matched, sent_ok=sent_ok, sent_fail=sent_fail, skipped=skipped, last=name)
                continue

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

            # 若需要圖片（且已確認可用）→ 依 send_text/send_image 組裝
            if send_image:
                if send_text:
                    messages.append(text_message)
                messages.append(image_message)

            if not messages:
                continue

            try:
                line_bot_api.push_message(user_id, messages)
                sent_ok += 1
                time.sleep(0.05)  # 保留你原本的節奏
            except Exception as e:
                sent_fail += 1
                print(f"[job:{job_id}] 發送訊息給 {user_id} 失敗: {e}")

        if (sent_ok + sent_fail + skipped) % 20 == 0:
            set_job(job_id, scanned=scanned, matched=matched, sent_ok=sent_ok, sent_fail=sent_fail, skipped=skipped, last=name)

    set_job(
        job_id,
        progress="finished",
        scanned=scanned,
        matched=matched,
        sent_ok=sent_ok,
        sent_fail=sent_fail,
        skipped=skipped,
    )

# 記錄最近處理過的事件，避免 LINE redelivery 重複寫
# (用 dict + 時間戳，避免額外套件)
PROCESSED = {}
PROCESSED_TTL_SEC = 3600  # 1 小時

def _gc_processed(now_ts: float):
    # 簡單清理過期 key
    expired = [k for k, t in PROCESSED.items() if now_ts - t > PROCESSED_TTL_SEC]
    for k in expired:
        PROCESSED.pop(k, None)

def seen_event(key: str) -> bool:
    now_ts = time.time()
    _gc_processed(now_ts)
    if not key:
        return False
    if key in PROCESSED:
        return True
    PROCESSED[key] = now_ts
    return False

def safe_append_rows(sheet, rows, retries=4):
    """
    用 append_rows 一次寫多筆，比 append_row 穩定、API 次數更少
    """
    for attempt in range(retries):
        try:
            with SHEET_LOCK:
                sheet.append_rows(rows, value_input_option="RAW")
            print(f"[sheet] appended {len(rows)} rows")
            return True
        except Exception as e:
            print(f"[sheet] append_rows failed {attempt+1}/{retries}: {e}")
            time.sleep(2 ** attempt)
    return False

def download_line_content_to_tempfile(message_id: str, suffix: str):
    """
    把 LINE 檔案/圖片用串流寫到 /tmp，避免一次把整張圖吃進記憶體。
    回傳 (filepath, mimetype)
    """
    message_content = line_bot_api.get_message_content(message_id)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="/tmp")
    try:
        # line-bot-sdk 的 content 物件通常支援 iter_content()
        if hasattr(message_content, "iter_content"):
            for chunk in message_content.iter_content():
                if chunk:
                    tmp.write(chunk)
        else:
            # fallback：真的沒有 iter_content 才用 .content
            tmp.write(message_content.content)

        tmp.flush()
        return tmp.name
    finally:
        tmp.close()

def event_worker():
    while True:
        request_id, event = EVENT_Q.get()
        info = extract_event_info(event)
        try:
            log_event("event_worker_start", request_id, info)

            # 用 webhookEventId 去重（最推薦），沒有就退回 message_id
            dedup_key = info.get("webhookEventId") or info.get("message_id") or ""
            if seen_event(dedup_key):
                log_event("event_skipped_duplicate", request_id, info)
                continue

            user_id = event["source"]["userId"]
            msg = event.get("message", {}) or {}
            message_type = msg.get("type", "")
            message_id = msg.get("id", "")

            taiwan_time = now_tw_str()
            new_user_flag = "new" if is_new_user(user_id) else ""
            user_name = get_user_name(user_id)

            # 先把「要寫入 sheet 的 row」準備好（先確保落地）
            rows_to_write = []

            if message_type == "text":
                message_text = msg.get("text", "")
                rows_to_write.append([taiwan_time, user_id, user_name, message_text, new_user_flag])
                safe_append_rows(sheet, rows_to_write)

            elif message_type == "image":
                rows_to_write.append([taiwan_time, user_id, user_name, f"image id: {message_id}", new_user_flag])
                safe_append_rows(sheet, rows_to_write)

                # 再做重活：下載 + 上傳 Drive
                class_name, std_name = get_class_std_from_user_id(user_id)
                file_name = f"{class_name}_{std_name}_{message_id}.jpg" if class_name and std_name else f"{message_id}.jpg"

                tmp_path = None
                try:
                    tmp_path = download_line_content_to_tempfile(message_id, suffix=".jpg")
                    with open(tmp_path, "rb") as f:
                        uploaded_file_id = upload_image_to_drive(f, file_name)
                    if uploaded_file_id:
                        log_event("drive_upload_ok", request_id, info, {"drive_file_id": uploaded_file_id, "file_name": file_name})
                    else:
                        log_event("drive_upload_fail", request_id, info, {"file_name": file_name})
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)

            elif message_type == "sticker":
                sticker_id = msg.get("stickerId", "")
                rows_to_write.append([taiwan_time, user_id, user_name, f"sticker id: {sticker_id}", new_user_flag])
                safe_append_rows(sheet, rows_to_write)

            elif message_type == "file":
                file_name = msg.get("fileName", "")
                file_name_lower = file_name.lower()

                # PDF
                if file_name and file_name_lower.endswith(".pdf"):
                    rows_to_write.append([
                        taiwan_time,
                        user_id,
                        user_name,
                        f"pdf: {file_name}",
                        new_user_flag
                    ])
                    safe_append_rows(sheet, rows_to_write)

                    class_name, std_name = get_class_std_from_user_id(user_id)
                    save_name = (
                        f"{class_name}_{std_name}_{file_name}"
                        if class_name and std_name
                        else file_name
                    )

                    tmp_path = None
                    try:
                        tmp_path = download_line_content_to_tempfile(
                            message_id,
                            suffix=".pdf"
                        )

                        with open(tmp_path, "rb") as f:
                            uploaded_pdf_id = upload_file_to_drive(
                                f,
                                save_name,
                                mimetype="application/pdf"
                            )

                        if uploaded_pdf_id:
                            log_event(
                                "drive_upload_ok",
                                request_id,
                                info,
                                {
                                    "drive_file_id": uploaded_pdf_id,
                                    "file_name": save_name
                                }
                            )
                        else:
                            log_event(
                                "drive_upload_fail",
                                request_id,
                                info,
                                {"file_name": save_name}
                            )

                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)

                # 圖片用「檔案」方式傳送
                elif file_name and file_name_lower.endswith((".jpg", ".jpeg", ".png")):
                    rows_to_write.append([
                        taiwan_time,
                        user_id,
                        user_name,
                        f"image file: {file_name}",
                        new_user_flag
                    ])
                    safe_append_rows(sheet, rows_to_write)

                    class_name, std_name = get_class_std_from_user_id(user_id)
                    save_name = (
                        f"{class_name}_{std_name}_{file_name}"
                        if class_name and std_name
                        else file_name
                    )

                    # 保留原本副檔名
                    suffix = os.path.splitext(file_name)[1]

                    if file_name_lower.endswith(".png"):
                        mimetype = "image/png"
                    else:
                        mimetype = "image/jpeg"

                    tmp_path = None
                    try:
                        tmp_path = download_line_content_to_tempfile(
                            message_id,
                            suffix=suffix
                        )

                        with open(tmp_path, "rb") as f:
                            uploaded_image_id = upload_file_to_drive(
                                f,
                                save_name,
                                mimetype=mimetype
                            )

                        if uploaded_image_id:
                            log_event(
                                "drive_upload_ok",
                                request_id,
                                info,
                                {
                                    "drive_file_id": uploaded_image_id,
                                    "file_name": save_name
                                }
                            )
                        else:
                            log_event(
                                "drive_upload_fail",
                                request_id,
                                info,
                                {"file_name": save_name}
                            )

                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)

            log_event("event_worker_ok", request_id, info)

        except Exception as e:
            log_event("event_worker_error", request_id, info, {"error": str(e)})
        finally:
            EVENT_Q.task_done()

_WORKER_STARTED = False
def ensure_worker_started():
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    t = threading.Thread(target=event_worker, daemon=True)
    t.start()
    _WORKER_STARTED = True
    print("[worker] started")

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

# =========================
# (C) /send：只排隊，立刻回應
# =========================
@app.route("/send", methods=["POST"])
def send_messages():
    ensure_job_worker_started()

    data = request.get_json() or {}
    std_class = (data.get("std_class") or "").strip()
    title = (data.get("title") or "").strip()

    if not std_class or not title:
        return jsonify({"error": "std_class 和 title 都必須提供"}), 400

    job_id = uuid.uuid4().hex[:10]
    set_job(job_id, status="queued", type="send", std_class=std_class, title=title, created_at=now_tw_str())

    try:
        JOB_Q.put_nowait({"job_id": job_id, "type": "send", "std_class": std_class, "title": title})
    except Exception:
        set_job(job_id, status="error", error="queue_full")
        return jsonify({"error": "queue_full"}), 503

    # ✅ 立刻回應，避免 gunicorn timeout
    return jsonify({"ok": True, "job_id": job_id, "status": "queued"}), 202


@app.route("/send_status/<job_id>", methods=["GET"])
def send_status(job_id):
    with JOBS_LOCK:
        info = JOBS.get(job_id)
    if not info:
        return jsonify({"error": "job_not_found"}), 404

    # 不回傳內部 _ts
    info2 = dict(info)
    info2.pop("_ts", None)
    return jsonify(info2), 200

@app.route("/notify", methods=["POST"])
def notify_messages():
    try:
        data = request.get_json() or {}

        image_names_raw = str(data.get("image_names", "")).strip()

        raw_message_texts = data.get("message_texts", [])
        if not isinstance(raw_message_texts, list):
            return jsonify({"error": "message_texts 必須是陣列"}), 400

        message_texts = [
            str(t).strip()
            for t in raw_message_texts
            if str(t).strip()
        ]

        order = str(data.get("order", "text-first")).strip()
        hw_value = str(data.get("hw_value", "y")).strip().lower()

        send_text = bool(message_texts)
        send_image = bool(image_names_raw)

        if not send_text and not send_image:
            return jsonify({"error": "請至少提供圖片名稱或文字訊息"}), 400

        if hw_value not in ("y", "a", "b"):
            return jsonify({"error": "hw_value 只允許 y、a、b"}), 400

        if order not in ("text-first", "image-first"):
            return jsonify({
                "error": "order 只允許 text-first 或 image-first"
            }), 400

        image_names = [
            urllib.parse.unquote(name.strip())
            for name in image_names_raw.split(",")
            if name.strip()
        ] if send_image else []

        text_messages = [
            TextSendMessage(text=t)
            for t in message_texts
        ]

        # 圖片存在性檢查
        if send_image:
            for img_name in image_names:
                image_url, image_url_pre = notify_image_urls(img_name)

                image_exists = False

                for i in range(2):
                    try:
                        response = requests.head(
                            image_url,
                            timeout=3,
                            allow_redirects=True
                        )

                        if response.status_code == 200:
                            image_exists = True
                            break

                    except Exception as e:
                        print(f"檢查圖片失敗 {i + 1} 次：{e}")

                    if i == 0:
                        time.sleep(1)

                if not image_exists:
                    print(f"❌ 終止：圖片不存在 - {image_url}")
                    return jsonify({
                        "error": f"圖片不存在：{img_name}"
                    }), 400

        # 讀取試算表
        with SHEET_LOCK:
            records = mail_sheet.get_all_records()

        matched_rows = 0
        target_count = 0
        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for row in records:
            row_hw = str(row.get("hw", "")).strip().lower()

            if row_hw != hw_value:
                continue

            matched_rows += 1

            id_field = str(row.get("id", "")).strip()

            if "," in id_field:
                user_ids = [
                    uid.strip()
                    for uid in id_field.split(",")
                    if uid.strip()
                ]
            else:
                user_ids = [id_field] if id_field else []

            if not user_ids:
                skipped_count += 1
                continue

            image_messages = []

            if send_image:
                for img_name in image_names:
                    image_url, image_url_pre = notify_image_urls(img_name)

                    image_messages.append(
                        ImageSendMessage(
                            original_content_url=image_url,
                            preview_image_url=image_url_pre
                        )
                    )

            for user_id in user_ids:
                target_count += 1

                messages = []

                if order == "text-first":
                    messages.extend(text_messages)
                    messages.extend(image_messages)
                else:
                    messages.extend(image_messages)
                    messages.extend(text_messages)

                if not messages:
                    skipped_count += 1
                    continue

                try:
                    line_bot_api.push_message(user_id, messages)
                    sent_count += 1
                    time.sleep(0.05)

                except Exception as e:
                    failed_count += 1
                    print(f"發送給 {user_id} 失敗：{e}")

        print(
            f"通知發送完成：hw={hw_value}，"
            f"符合資料列={matched_rows}，"
            f"目標帳號={target_count}，"
            f"成功={sent_count}，"
            f"失敗={failed_count}，"
            f"略過={skipped_count}"
        )

        return jsonify({
            "message": "Notify messages sent!",
            "hw_value": hw_value,
            "matched_rows": matched_rows,
            "target_count": target_count,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count
        }), 200

    except Exception as e:
        print(f"❌ notify 發生錯誤：{e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["POST"])
def linebot():
    body = request.get_data(as_text=True)
    request_id = uuid.uuid4().hex[:8]

    try:
        ensure_worker_started()

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
            log_event("event_enqueued", request_id, info)

            # queue 滿了要明確記錄，否則會默默丟失
            try:
                EVENT_Q.put_nowait((request_id, event))
            except Exception as e:
                log_event("queue_full_drop", request_id, info, {"error": str(e)})

        # ✅ 關鍵：立刻回 200，避免 gunicorn timeout 造成整批事件中斷
        return "OK", 200

    except Exception as e:
        print(json.dumps({
            "tag": "webhook_parse_error",
            "request_id": request_id,
            "tw_time": now_tw_str(),
            "error": str(e)
        }, ensure_ascii=False))
        # 解析失敗也回 200（避免 LINE 一直重送炸你）
        return "OK", 200

# ==========================================
# 講義地址調查：只接受授權 POST，不允許公開 GET 觸發群發
# 管理文字由 KnownHost / InfinityFree PHP 提供
# ==========================================
LECTURE_REQUESTS = {}
LECTURE_REQUESTS_LOCK = threading.Lock()
LECTURE_FORM_URL = "https://iread327form.lovestoblog.com/address-form.php"
LECTURE_SHEET_ID = "14TwhcFFfW3B4323jWcdAIaOoGey6Qk8p2pdw0j0-UwE"


def lecture_authorized():
    expected = os.getenv("LECTURE_API_KEY", "")
    supplied = request.headers.get("X-Lecture-Key", "")
    return len(expected) >= 32 and secrets.compare_digest(expected, supplied)


def lecture_recipients():
    # 完全保留原本欄位規則：A=user ID、B=班級、H=code、I=send_flag
    with SHEET_LOCK:
        rows = gc.open_by_key(LECTURE_SHEET_ID).sheet1.get_all_values()
    targets = []
    for row in rows:
        if len(row) < 9:
            continue
        user_id, class_info, code, flag = row[0].strip(), row[1].strip(), row[7].strip(), row[8].strip().lower()
        if "線上" in class_info and user_id and code and flag == "y":
            targets.append((user_id, code))
    return targets


def _do_lecture(payload: dict, job_id: str):
    targets = lecture_recipients()
    sent_ok, sent_fail = 0, 0
    set_job(job_id, progress="sending", eligible_count=len(targets), sent_ok=0, sent_fail=0)
    for user_id, code in targets:
        # 安全地把個別 code 放在 query string，連結只由伺服器產生
        url = LECTURE_FORM_URL + "?code=" + urllib.parse.quote(code, safe="") + "&v=2"
        second = payload["message2"].replace("{{url}}", url)
        if len(second) > 5000:
            sent_fail += 1
            continue
        try:
            line_bot_api.push_message(user_id, [
                TextSendMessage(text=payload["message1"]),
                TextSendMessage(text=second),
            ])
            sent_ok += 1
            time.sleep(0.05)
        except Exception as e:
            sent_fail += 1
            print(f"[lecture:{job_id}] LINE push failed: {type(e).__name__}", flush=True)
        if (sent_ok + sent_fail) % 10 == 0:
            set_job(job_id, sent_ok=sent_ok, sent_fail=sent_fail)
    set_job(job_id, sent_ok=sent_ok, sent_fail=sent_fail, progress="finished")
    print(f"[lecture:{job_id}] finished: eligible={len(targets)}, ok={sent_ok}, fail={sent_fail}", flush=True)
    if sent_fail:
        raise RuntimeError(f"Partially sent: {sent_fail} failures; review before retrying")


@app.route("/lecture", methods=["GET", "POST"])
def lecture_dispatch():
    if request.method == "GET":
        return jsonify({"error": "GET sending disabled. Use authenticated PHP management page."}), 405
    if not lecture_authorized():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "")).strip()
    a = str(data.get("message1", "")).strip()
    b = str(data.get("message2", "")).strip()
    if mode not in ("preview", "send") or not a or not b or "{{url}}" not in b or len(a) > 4000 or len(b) > 4000:
        return jsonify({"error": "Invalid message template; message2 must include {{url}}"}), 400
    if mode == "preview":
        try:
            targets = lecture_recipients()
            return jsonify({"eligible_count": len(targets)}), 200
        except Exception as e:
            print(f"[lecture] preview failed: {type(e).__name__}", flush=True)
            return jsonify({"error": "Unable to read recipient list"}), 503
    request_key = str(data.get("request_key", ""))
    if not re.fullmatch(r"[a-f0-9]{32}", request_key):
        return jsonify({"error": "Invalid request_key"}), 400
    ensure_job_worker_started()
    with LECTURE_REQUESTS_LOCK:
        if request_key in LECTURE_REQUESTS:
            return jsonify({"ok": True, "job_id": LECTURE_REQUESTS[request_key], "status": "already_queued"}), 202
        if JOB_Q.full():
            return jsonify({"error": "queue_full"}), 503
        jid = uuid.uuid4().hex[:10]
        set_job(jid, type="lecture", status="queued", created_at=now_tw_str())
        LECTURE_REQUESTS[request_key] = jid
        JOB_Q.put_nowait({"job_id": jid, "type": "lecture", "payload": {"message1": a, "message2": b}})
    return jsonify({"ok": True, "job_id": jid, "status": "queued"}), 202


@app.route("/lecture_status/<job_id>", methods=["GET"])
def lecture_status(job_id):
    if not lecture_authorized():
        return jsonify({"error": "unauthorized"}), 401
    with JOBS_LOCK:
        data = dict(JOBS.get(job_id, {}))
    if not data or data.get("type") != "lecture":
        return jsonify({"error": "job_not_found_or_expired"}), 404
    data.pop("_ts", None)
    return jsonify(data), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
