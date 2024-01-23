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

    image_url = "https://steam.oxxostudio.tw/download/python/line-rich-menu-demo.jpg"
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
                    line_bot_api.set_rich_menu_image(
                        "richmenu-b04102d54c3ba22bada7e26fe26215b1",
                        "image/jpeg",
                        image_buffer,
                    )
            headers = {
                "Authorization": "Bearer 1PlQGmb524SP8EccC6ZKIvX47fzf0u9pRZy0E4oCjx71d5gTBTy2U+JzlcfWMc10r4haBWSJHSv7kIE/cnRCnFM6VNtF3CMmTzVAR7n7xtlyiJs3RuuMXhPq+xOv4f9IJontF4iVL8amDiYMJlUxCAdB04t89/1O/w1cDnyilFU="
            }
            body2 = {
                "size": {"width": 2500, "height": 1686},  # 設定尺寸
                "selected": "true",  # 預設是否顯示
                "name": "Richmenu demo",  # 選單名稱
                "chatBarText": "Richmenu demo",  # 選單在 LINE 顯示的標題
                "areas": [  # 選單內容
                    {
                        "bounds": {
                            "x": 341,
                            "y": 75,
                            "width": 560,
                            "height": 340,
                        },  # 選單位置與大小
                        "action": {"type": "message", "text": "電器"},  # 點擊後傳送文字
                    },
                    {
                        "bounds": {"x": 1434, "y": 229, "width": 930, "height": 340},
                        "action": {
                            "type": "uri",
                            "label": "運動用品",
                            "uri": "https://www.oxxostudio.tw",
                        },  # 點擊後開啟網頁
                    },
                    {
                        "bounds": {"x": 122, "y": 641, "width": 560, "height": 340},
                        "action": {"type": "message", "text": "客服"},
                    },
                    {
                        "bounds": {"x": 1012, "y": 645, "width": 560, "height": 340},
                        "action": {"type": "message", "text": "餐廳"},
                    },
                    {
                        "bounds": {"x": 1813, "y": 677, "width": 560, "height": 340},
                        "action": {"type": "message", "text": "鞋子"},
                    },
                    {
                        "bounds": {"x": 423, "y": 1203, "width": 560, "height": 340},
                        "action": {"type": "message", "text": "美食"},
                    },
                    {
                        "bounds": {"x": 1581, "y": 1133, "width": 560, "height": 340},
                        "action": {"type": "message", "text": "衣服"},
                    },
                ],
            }
            req = requests.request(
                "POST",
                "https://api.line.me/v2/bot/user/all/richmenu/richmenu-b04102d54c3ba22bada7e26fe26215b1",
                headers=headers,
                data=json.dumps(body2).encode("utf-8"),
            )

            print(req.text)

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
