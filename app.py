import json, os, requests, time, pytz
from datetime import datetime
from io import BytesIO
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

now = datetime.now()

# 设置时区为台湾（东八区，+08:00）
timezone = pytz.timezone("Asia/Taipei")
now_with_timezone = now.replace(tzinfo=timezone)

# 格式化输出
formatted_time = now_with_timezone.strftime("%Y-%m-%dT%H:%M:%S%z")
    
app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def linebot():
    

    body = request.get_data(as_text=True)
    json_data = json.loads(body)

    # print(json_data)

    try:
        line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
        handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
        # openai.api_key = os.getenv('OPENAI_API_KEY')

        signature = request.headers["X-Line-Signature"]
        handler.handle(body, signature)

        tp = json_data["events"][0]["message"]["type"]
        tk = json_data["events"][0]["replyToken"]  # 取得 reply token

        if tp == "text":

            if (
                json_data["events"][0]["message"]["text"] == "雷達回波圖"
                or json_data["events"][0]["message"]["text"] == "雷達回波"
            ):  # 如果是雷達回波圖相關的文字
                # 傳送雷達回波圖 ( 加上時間戳記 )
                radar_url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0058-003?Authorization=CWA-DAEAB112-B74E-41D8-B951-527F63665E26&format=JSON"
                radar = requests.get(radar_url)        # 爬取資料
                radar_json = radar.json()              # 使用 JSON 格式
                radar_img = radar_json['cwaopendata']['dataset']['resource']['ProductURL']  # 取得圖片網址
                reply_image(
                    radar_img,
                    tk,
                    os.getenv("CHANNEL_ACCESS_TOKEN"),
                )

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"



if __name__ == "__main__":
    app.run()


def reply_image(msg, rk, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "replyToken": rk,
        "messages": [
            {"type": "image", "originalContentUrl": msg + "?" + formatted_time, "previewImageUrl": msg + "?" + formatted_time}
        ],
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )
