import json
import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)

@app.route("/callback", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)
    json_data = json.loads(body)
    # print(json_data)
    
    try:
        line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
        handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
        # openai.api_key = os.getenv('OPENAI_API_KEY')
        
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        
        tp = json_data['events'][0]['message']['type']
        tk = json_data['events'][0]['replyToken']      # 取得 reply token
        
        if tp == 'text':
            msg = json_data['events'][0]['message']['text']  # 取得 LINE 收到的文字訊息
            reply = msg
        # 判斷如果是圖片
        elif tp == 'image':
            msgID = json_data['events'][0]['message']['id']  # 取得訊息 id
            message_content = line_bot_api.get_message_content(msgID)  # 根據訊息 ID 取得訊息內容
            # 在同樣的資料夾中建立以訊息 ID 為檔名的 .jpg 檔案
            with open(f'{msgID}.jpg', 'wb') as fd:
                fd.write(message_content.content)             # 以二進位的方式寫入檔案
            reply = '圖片儲存完成！'                             # 設定要回傳的訊息
        else:
            reply = '你傳的不是文字或圖片呦～'
        print(reply)
    except:
        print(body)                                            # 如果發生錯誤，印出收到的內容
    return 'OK'   
      
if __name__ == "__main__":
    app.run()
