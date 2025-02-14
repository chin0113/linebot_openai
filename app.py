from flask import Flask, request
import json
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Google Sheets API 的憑證檔案
CREDENTIALS_FILE = "newagent-gfvg-4f6c0497de66.json"
SPREADSHEET_NAME = "LineMessages"  # 試算表名稱（請確保你已創建該試算表）

# 設定 Google Sheets API 的授權
credentials = Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(credentials)

# 開啟試算表（確保服務帳戶已獲得試算表的編輯權限）
sheet = gc.open(SPREADSHEET_NAME).sheet1

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
