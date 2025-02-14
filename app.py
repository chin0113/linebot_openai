from flask import Flask, request
import json
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment
from datetime import datetime, timedelta
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import MessagingApi, Configuration, MessagingApiBlob
from linebot.v3.messaging.api_client import ApiClient
import os
import uuid
from pathlib import Path

app = Flask(__name__)

# 使用環境變數來存取 LINE API 金鑰
ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
SECRET = os.getenv("LINE_SECRET")

# 初始化 LINE Messaging API
config = Configuration(access_token=ACCESS_TOKEN)
messaging_api = MessagingApi(api_client=ApiClient(configuration=config))
messaging_api_blob = MessagingApiBlob(api_client=ApiClient(configuration=config))
handler = WebhookHandler(channel_secret=SECRET)

# 文件路徑
home = Path.home()
base_path = home / "Downloads" / "行雲流水"

OUTPUT_PATH = base_path / "output_heroku.xlsx"
ID_FILE_PATH = base_path / "id.xlsx"
DOWNLOAD_PATH = base_path / "作業"

# 初始化 Excel 文件
def initialize_excel():
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Messages"
        ws.append(["DateTime (Taiwan)", "User ID", "User Name", "Message Type", "Message Content"])
        for col in ws.columns:
            for cell in col:
                cell.alignment = Alignment(horizontal='center')
        wb.save(OUTPUT_PATH)
    except Exception as e:
        print(f"初始化 Excel 失敗: {e}")

if not os.path.exists(OUTPUT_PATH):
    initialize_excel()

# 加載 ID 對應
def load_id_mapping(file_path):
    id_mapping = {}
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            user_id = row[2]
            part1 = row[3] if row[3] else ""
            part2 = row[4] if row[4] else ""
            custom_name = part1 + "-" + part2
            if user_id and custom_name:
                id_mapping[user_id] = custom_name
    except Exception as e:
        print(f"載入 id.xlsx 時發生錯誤: {e}")
    return id_mapping

id_mapping = load_id_mapping(ID_FILE_PATH)

@app.route("/", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    try:
        handler.handle(body=body, signature=signature)
        json_data = json.loads(body)
        event = json_data['events'][0]

        message_type = event['message']['type']
        message_id = event['message']['id']
        user_id = event['source']['userId']
        user_profile = messaging_api.get_profile(user_id)
        user_name = user_profile.display_name
        file_name = id_mapping.get(user_id, user_id)

        timestamp_ms = event['timestamp']
        timestamp_dt = datetime.utcfromtimestamp(timestamp_ms / 1000) + timedelta(hours=8)
        formatted_time = timestamp_dt.strftime('%Y-%m-%d_%H-%M-%S')

        if message_type == 'text':
            message_content = event['message']['text']
            message_type_str = 'Text'
        elif message_type == 'sticker':
            sticker_id = event['message']['stickerId']
            package_id = event['message']['packageId']
            message_content = f"Sticker ID: {sticker_id}, Package ID: {package_id}"
            message_type_str = 'Sticker'
        elif message_type in ['image', 'file']:
            file_extension = 'jpg' if message_type == 'image' else event['message']['fileName'].split('.')[-1]
            unique_id = uuid.uuid4().hex
            download_file_name = f"{file_name}_{formatted_time}_{unique_id}.{file_extension}"
            file_path = os.path.join(DOWNLOAD_PATH, download_file_name)

            try:
                content_response = messaging_api_blob.get_message_content(message_id)
                with open(file_path, "wb") as f:
                    for chunk in content_response.iter_content():
                        f.write(chunk)
                print(f"文件已下載: {file_path}")
            except Exception as e:
                print(f"下載失敗: {e}")

            message_content = f"Downloaded file: {download_file_name}"
            message_type_str = message_type.capitalize()
        else:
            message_content = f"未知消息類型: {message_type}"
            message_type_str = 'Unknown'

    except InvalidSignatureError:
        print("Invalid Signature")

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
