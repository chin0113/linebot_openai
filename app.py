import json
import os
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
            line_bot_api.push_message(
                "U2574668b48e37ef5423509b4e2355321",
                FlexSendMessage(
                    alt_text="hello",
                    contents={
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/01_1_cafe.png",
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover",
                            "action": {"type": "uri", "uri": "http://linecorp.com/"},
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "Brown Cafe",
                                    "weight": "bold",
                                    "size": "xl",
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "margin": "md",
                                    "contents": [
                                        {
                                            "type": "icon",
                                            "size": "sm",
                                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png",
                                        },
                                        {
                                            "type": "icon",
                                            "size": "sm",
                                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png",
                                        },
                                        {
                                            "type": "icon",
                                            "size": "sm",
                                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png",
                                        },
                                        {
                                            "type": "icon",
                                            "size": "sm",
                                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png",
                                        },
                                        {
                                            "type": "icon",
                                            "size": "sm",
                                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gray_star_28.png",
                                        },
                                        {
                                            "type": "text",
                                            "text": "4.0",
                                            "size": "sm",
                                            "color": "#999999",
                                            "margin": "md",
                                            "flex": 0,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "margin": "lg",
                                    "spacing": "sm",
                                    "contents": [
                                        {
                                            "type": "box",
                                            "layout": "baseline",
                                            "spacing": "sm",
                                            "contents": [
                                                {
                                                    "type": "text",
                                                    "text": "Place",
                                                    "color": "#aaaaaa",
                                                    "size": "sm",
                                                    "flex": 1,
                                                },
                                                {
                                                    "type": "text",
                                                    "text": "Miraina Tower, 4-1-6 Shinjuku, Tokyo",
                                                    "wrap": True,
                                                    "color": "#666666",
                                                    "size": "sm",
                                                    "flex": 5,
                                                },
                                            ],
                                        },
                                        {
                                            "type": "box",
                                            "layout": "baseline",
                                            "spacing": "sm",
                                            "contents": [
                                                {
                                                    "type": "text",
                                                    "text": "Time",
                                                    "color": "#aaaaaa",
                                                    "size": "sm",
                                                    "flex": 1,
                                                },
                                                {
                                                    "type": "text",
                                                    "text": "10:00 - 23:00",
                                                    "wrap": True,
                                                    "color": "#666666",
                                                    "size": "sm",
                                                    "flex": 5,
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "button",
                                    "style": "link",
                                    "height": "sm",
                                    "action": {
                                        "type": "uri",
                                        "label": "CALL",
                                        "uri": "https://linecorp.com",
                                    },
                                },
                                {
                                    "type": "button",
                                    "style": "link",
                                    "height": "sm",
                                    "action": {
                                        "type": "uri",
                                        "label": "WEBSITE",
                                        "uri": "https://linecorp.com",
                                    },
                                },
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "contents": [],
                                    "margin": "sm",
                                },
                            ],
                            "flex": 0,
                        },
                    },
                ),
            )

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
