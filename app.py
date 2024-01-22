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
                TemplateSendMessage(
                    alt_text="ImageCarousel template",
                    template=ImageCarouselTemplate(
                        columns=[
                            ImageCarouselColumn(
                                image_url="https://upload.wikimedia.org/wikipedia/en/a/a6/Pok%C3%A9mon_Pikachu_art.png",
                                action=MessageAction(label="皮卡丘", text="皮卡丘"),
                            ),
                            ImageCarouselColumn(
                                image_url="https://upload.wikimedia.org/wikipedia/en/5/59/Pok%C3%A9mon_Squirtle_art.png",
                                action=MessageAction(label="傑尼龜", text="傑尼龜"),
                            ),
                        ]
                    ),
                ),
            )

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
