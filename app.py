import json, os, requests, time, pytz
from datetime import datetime
from io import BytesIO
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

# now = datetime.now()

# 设置时区为台湾（东八区，+08:00）
mytz = pytz.timezone("Asia/Taipei")
# now_with_timezone = now.replace(tzinfo=timezone)
mytime = mytz.localize(datetime.now())

# 格式化输出
formatted_time = mytime.strftime("%Y-%m-%dT%H:%M:%S%z")

app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def linebot():

    body = request.get_data(as_text=True)
    json_data = json.loads(body)

    print(json_data)

    try:
        line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
        handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
        # openai.api_key = os.getenv('OPENAI_API_KEY')

        signature = request.headers["X-Line-Signature"]
        handler.handle(body, signature)

        tp = json_data["events"][0]["message"]["type"]
        tk = json_data["events"][0]["replyToken"]  # 取得 reply token
        if json_data["events"][0]["source"]["type"] == "group":
            group_id = json_data["events"][0]["source"]["groupId"]
        else:
            group_id = ""
        user_id = json_data["events"][0]["source"]["userId"]

        if tp == "text":

            if (
                json_data["events"][0]["message"]["text"] == "雷達回波圖"
                or json_data["events"][0]["message"]["text"] == "雷達回波"
            ):  # 如果是雷達回波圖相關的文字
                # 傳送雷達回波圖 ( 加上時間戳記 )
                radar_url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0058-003?Authorization=CWA-DAEAB112-B74E-41D8-B951-527F63665E26&format=JSON"
                radar = requests.get(radar_url)  # 爬取資料
                radar_json = radar.json()  # 使用 JSON 格式
                radar_img = radar_json["cwaopendata"]["dataset"]["resource"][
                    "ProductURL"
                ]  # 取得圖片網址
                reply_image(
                    radar_img,
                    tk,
                    os.getenv("CHANNEL_ACCESS_TOKEN")
                )
            elif (
                json_data["events"][0]["message"]["text"] == "地震"
                or json_data["events"][0]["message"]["text"] == "地震資訊"
            ):
                e_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization=CWA-DAEAB112-B74E-41D8-B951-527F63665E26"
                e_data = requests.get(e_url)  # 爬取地震資訊網址
                e_data_json = e_data.json()  # json 格式化訊息內容
                eq = e_data_json["records"]["Earthquake"]  # 取出地震資訊
                for i in eq:
                    loc = i["EarthquakeInfo"]["Epicenter"]["Location"]  # 地震地點
                    val = i["EarthquakeInfo"]["EarthquakeMagnitude"]["MagnitudeValue"]  # 地震規模
                    dep = i["EarthquakeInfo"]["FocalDepth"]  # 地震深度
                    eq_time = i["EarthquakeInfo"]["OriginTime"]  # 地震時間
                    img = i["ReportImageURI"]  # 地震圖
                    msg = [f"{loc}，芮氏規模 {val} 級，深度 {dep} 公里，發生時間 {eq_time}。", img]
                    break  # 取出第一筆資料後就 break

                push_message(
                    msg[0],
                    user_id,
                    os.getenv("CHANNEL_ACCESS_TOKEN")
                )
                reply_image(
                    msg[1], 
                    tk, 
                    os.getenv("CHANNEL_ACCESS_TOKEN")
                )
            if group_id == "C3d46bba7313debd676bf4f3d29c28097":
                line_bot_api.push_message('C97faa0f580dc2e0964a7079ae67b56e7',TextSendMessage(json_data["events"][0]["message"]["text"]))
            elif group_id == "C97faa0f580dc2e0964a7079ae67b56e7":
                line_bot_api.push_message('C3d46bba7313debd676bf4f3d29c28097',TextSendMessage(json_data["events"][0]["message"]["text"]))
            

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()


def reply_image(msg, rk, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "replyToken": rk,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": msg + "?" + formatted_time,
                "previewImageUrl": msg + "?" + formatted_time,
            }
        ]
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body).encode("utf-8")
    )


def push_message(msg, uid, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "to": uid, 
        "messages": [
            {
                "type": "text", 
                "text": msg
            }
        ]
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        data=json.dumps(body).encode("utf-8")
    )
