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
            line_bot_api.push_message('U2574668b48e37ef5423509b4e2355321', TemplateSendMessage(
                alt_text='CarouselTemplate',
                template=CarouselTemplate(
                    columns=[
                        CarouselColumn(
                            thumbnail_image_url='https://steam.oxxostudio.tw/download/python/line-template-message-demo.jpg',
                            title='選單 1',
                            text='說明文字 1',
                            actions=[
                                PostbackAction(
                                    label='postback',
                                    data='data1'
                                ),
                                MessageAction(
                                    label='hello',
                                    text='hello'
                                ),
                                URIAction(
                                    label='oxxo.studio',
                                    uri='http://oxxo.studio'
                                )
                            ]
                        ),
                        CarouselColumn(
                            thumbnail_image_url='https://steam.oxxostudio.tw/download/python/line-template-message-demo2.jpg',
                            title='選單 2',
                            text='說明文字 2',
                            actions=[
                                PostbackAction(
                                    label='postback',
                                    data='data1'
                                ),
                                MessageAction(
                                    label='hi',
                                    text='hi'
                                ),
                                URIAction(
                                    label='STEAM 教育學習網',
                                    uri='https://steam.oxxostudio.tw'
                                )
                            ]
                        )
                    ]
                )
            ))
            
    except Exception as error:
        print(error)                                            # 如果發生錯誤，印出收到的內容
    return 'OK'   


    
if __name__ == "__main__":
    app.run()
