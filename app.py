import json
import os
import requests
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
    
    image_url = 'https://steam.oxxostudio.tw/download/python/line-rich-menu-switch-demo-a.jpg'
    image_response = requests.get(image_url)
    
    if image_response.status_code == 200:
        with BytesIO(image_response.content) as image_buffer:
            line_bot_api.set_rich_menu_image('richmenu-bbe5902cc4e8d577e8c0f55a8d3af91b', 'image/jpeg', image_buffer)
    # print(json_data)

    try:
        line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
        handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
        # openai.api_key = os.getenv('OPENAI_API_KEY')

        signature = request.headers["X-Line-Signature"]
        handler.handle(body, signature)

        tp = json_data["events"][0]["message"]["type"]
        tk = json_data["events"][0]["replyToken"]  # 取得 reply token

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
