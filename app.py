import json
import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def linebot():
    headers = {
        "Authorization": "Bearer 1PlQGmb524SP8EccC6ZKIvX47fzf0u9pRZy0E4oCjx71d5gTBTy2U+JzlcfWMc10r4haBWSJHSv7kIE/cnRCnFM6VNtF3CMmTzVAR7n7xtlyiJs3RuuMXhPq+xOv4f9IJontF4iVL8amDiYMJlUxCAdB04t89/1O/w1cDnyilFU=",
        "Content-Type": "application/json",
    }
    body = {
        "size": {"width": 2500, "height": 1686},  # 設定尺寸
        "selected": "true",  # 預設是否顯示
        "name": "Richmenu demo",  # 選單名稱
        "chatBarText": "Richmenu demo",  # 選單在 LINE 顯示的標題
        "areas": [  # 選單內容
            {
                "bounds": {"x": 341, "y": 75, "width": 560, "height": 340},  # 選單位置與大小
                "action": {"type": "message", "text": "電器"},  # 點擊後傳送文字
            },
            {
                "bounds": {"x": 1434, "y": 229, "width": 930, "height": 340},
                "action": {"type": "message", "text": "運動用品"},
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


# 向指定網址發送 request
req = requests.request(
    "POST",
    "https://test01-1fbw.onrender.com/callback",
    headers=headers,
    data=json.dumps(body).encode("utf-8"),
)
# 印出得到的結果
print(req.text)


if __name__ == "__main__":
    app.run()
