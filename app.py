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
    try:
        line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
        handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
        # openai.api_key = os.getenv('OPENAI_API_KEY')
        
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        
        tp = json_data['events'][0]['message']['type']
        tk = json_data['events'][0]['replyToken']      # 取得 reply token
        
        if tp == 'text':
            msg = json_data['events'][0]['message']['text']
            
            img_url = reply_img(msg)
            location_dect = reply_location(msg)
            
            if img_url:
            # 如果有圖片網址，回傳圖片
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                line_bot_api.reply_message(tk,img_message)
            elif location_dect:
                location_message = LocationSendMessage(title=location_dect['title'],
                                                  address=location_dect['address'],
                                                  latitude=location_dect['latitude'],
                                                  longitude=location_dect['longitude'])
                line_bot_api.reply_message(tk,location_message)
            else:
                line_bot_api.reply_message(tk,TextSendMessage(msg))
            
        if tp == 'sticker':
            stickerId = json_data['events'][0]['message']['stickerId'] # 取得 stickerId
            packageId = json_data['events'][0]['message']['packageId'] # 取得 packageId
            sticker_message = StickerSendMessage(sticker_id=stickerId, package_id=packageId) # 設定要回傳的表情貼圖
            line_bot_api.reply_message(tk,sticker_message)  # 回傳訊息
    except:
        print(json_data)
    return 'OK'

def reply_img(text):
    img = {
        '皮卡丘':'https://upload.wikimedia.org/wikipedia/en/a/a6/Pok%C3%A9mon_Pikachu_art.png',
        '傑尼龜':'https://upload.wikimedia.org/wikipedia/en/5/59/Pok%C3%A9mon_Squirtle_art.png'
    }
    if text in img:
      return img[text]
    else:
      # 如果找不到對應的圖片，回傳 False
      return False

def reply_location(text):
    # 建立地點與文字對應的字典
    location = {
        '101':{
            'title':'台北 101',
            'address':'110台北市信義區信義路五段7號',
            'latitude':'25.034095712145003',
            'longitude':'121.56489941996108'
        },
        '總統府':{
            'title':'總統府',
            'address':'100台北市中正區重慶南路一段122號',
            'latitude':'25.040319874750914',
            'longitude':'121.51162883484746'
        }
    }
    if text in location:
      return location[text]
    else:
      # 如果找不到對應的地點，回傳 False
      return False
      
if __name__ == "__main__":
    app.run()
