import json
import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)

@app.route("/callback")
def linebot():
    line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
    
    try:
        msg = request.args.get('msg')
        if msg == '1':
            # 如果 msg 等於 1，發送文字訊息
            line_bot_api.push_message('U2574668b48e37ef5423509b4e2355321', TextSendMessage(text='hello'))
        elif msg == '2':
            # 如果 msg 等於 2，發送表情貼圖
            line_bot_api.push_message('U2574668b48e37ef5423509b4e2355321', StickerSendMessage(package_id=1, sticker_id=2))
    except:
        print("error")
    return 'OK'
      
if __name__ == "__main__":
    app.run()
