import json, os, requests, time
from io import BytesIO
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

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
                reply_image(
                    f"https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-005.png?{time.time_ns()}",
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
            {"type": "image", "originalContentUrl": msg, "previewImageUrl": msg}
        ],
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )
    print(req.text)
