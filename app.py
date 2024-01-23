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
    
    image_url = 'https://steam.oxxostudio.tw/download/python/line-rich-menu-demo.jpg'
    image_response = requests.get(image_url)

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
            if image_response.status_code == 200:
                with BytesIO(image_response.content) as image_buffer:
                    line_bot_api.set_rich_menu_image('richmenu-b04102d54c3ba22bada7e26fe26215b1', 'image/jpeg', image_buffer)
            headers = {'Authorization':'Bearer 1PlQGmb524SP8EccC6ZKIvX47fzf0u9pRZy0E4oCjx71d5gTBTy2U+JzlcfWMc10r4haBWSJHSv7kIE/cnRCnFM6VNtF3CMmTzVAR7n7xtlyiJs3RuuMXhPq+xOv4f9IJontF4iVL8amDiYMJlUxCAdB04t89/1O/w1cDnyilFU='}
            req = requests.request('POST', 'https://api.line.me/v2/bot/user/all/richmenu/richmenu-b04102d54c3ba22bada7e26fe26215b1', headers=headers)

            print(req.text)

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
