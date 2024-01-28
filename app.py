import json, os, requests, time, pytz, statistics
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


def reply_message(msg, rk, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "replyToken": rk, 
        "messages": [
            {
                "type": "text", 
                "text": msg
            }
        ]
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )


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
        ],
    }
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )


def push_message(msg, uid, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    req = requests.request(
        "POST",
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )


def current_weather(address):
    city_list, area_list, area_list2 = {}, {}, {}  # 定義好待會要用的變數
    msg = "找不到氣象資訊。"  # 預設回傳訊息

    # 定義取得資料的函式
    def get_data(url):
        w_data = requests.get(url)  # 爬取目前天氣網址的資料
        w_data_json = w_data.json()  # json 格式化訊息內容
        location = w_data_json["cwaopendata"]["dataset"]["Station"]  # 取出對應地點的內容

        for i in location:
            # name = i['Station']['StationName']               # 測站地點
            city = i["GeoInfo"]["CountyName"]  # 縣市名稱
            area = i["GeoInfo"]["TownName"]  # 鄉鎮行政區

            temp = check_data(i["WeatherElement"]["AirTemperature"])  # 氣溫
            humd = check_data(i["WeatherElement"]["RelativeHumidity"])  # 相對濕度
            r24 = check_data(i["WeatherElement"]["Now"]["Precipitation"])  # 累積雨量

            if area not in area_list:
                area_list[area] = {
                    "temp": temp,
                    "humd": humd,
                    "r24": r24,
                }  # 以鄉鎮區域為 key，儲存需要的資訊

            if city not in city_list:
                city_list[city] = {
                    "temp": [],
                    "humd": [],
                    "r24": [],
                }  # 以主要縣市名稱為 key，準備紀錄裡面所有鄉鎮的數值

            city_list[city]["temp"].append(temp)  # 記錄主要縣市裡鄉鎮區域的溫度 ( 串列格式 )
            city_list[city]["humd"].append(humd)  # 記錄主要縣市裡鄉鎮區域的濕度 ( 串列格式 )
            city_list[city]["r24"].append(r24)  # 記錄主要縣市裡鄉鎮區域的雨量 ( 串列格式 )

    # 定義如果數值小於 0，回傳 False 的函式
    def check_data(e):
        return False if float(e) < 0 else float(e)

    def msg_content(loc, msg):
        a = msg
        for i in loc:
            if i in address:  # 如果地址裡存在 key 的名稱
                temp = f"氣溫 {loc[i]['temp']} 度，" if loc[i]["temp"] != False else ""
                humd = f"相對濕度 {loc[i]['humd']}%，" if loc[i]["humd"] != False else ""
                r24 = f"累積雨量 {loc[i]['r24']}mm" if loc[i]["r24"] != False else ""
                description = f"{temp}{humd}{r24}".strip("，")
                a = f"{description}。"  # 取出 key 的內容作為回傳訊息使用
                break
        return a

    try:
        # 因為目前天氣有兩組網址，兩組都爬取
        code = "CWA-DAEAB112-B74E-41D8-B951-527F63665E26"
        get_data(
            f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0001-001?Authorization={code}&downloadType=WEB&format=JSON"
        )
        get_data(
            f"https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0003-001?Authorization={code}&downloadType=WEB&format=JSON"
        )

        for i in city_list:
            if (
                i not in area_list2
            ):  # 將主要縣市裡的數值平均後，以主要縣市名稱為 key，再度儲存一次，如果找不到鄉鎮區域，就使用平均數值
                area_list2[i] = {
                    "temp": round(statistics.mean(city_list[i]["temp"]), 1),
                    "humd": round(statistics.mean(city_list[i]["humd"]), 1),
                    "r24": round(statistics.mean(city_list[i]["r24"]), 1),
                }
        msg = msg_content(area_list2, msg)  # 將訊息改為「大縣市」
        msg = msg_content(area_list, msg)  # 將訊息改為「鄉鎮區域」
        return msg  # 回傳 msg
    except:
        return msg  # 如果取資料有發生錯誤，直接回傳 msg


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
        
        line_bot_api.reply_message(tk, TextSendMessage("hi"))
        
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
                reply_image(radar_img, tk, os.getenv("CHANNEL_ACCESS_TOKEN"))
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
                    val = i["EarthquakeInfo"]["EarthquakeMagnitude"][
                        "MagnitudeValue"
                    ]  # 地震規模
                    dep = i["EarthquakeInfo"]["FocalDepth"]  # 地震深度
                    eq_time = i["EarthquakeInfo"]["OriginTime"]  # 地震時間
                    img = i["ReportImageURI"]  # 地震圖
                    msg = [f"{loc}，芮氏規模 {val} 級，深度 {dep} 公里，發生時間 {eq_time}。", img]
                    break  # 取出第一筆資料後就 break
                
                # push_message(msg[0], user_id, os.getenv("CHANNEL_ACCESS_TOKEN"))
                reply_arr=[]
                reply_arr.append(TextSendMessage(msg[0]))
                reply_arr.append(ImageSendMessage(original_content_url=msg[1], preview_image_url=msg[1]))
                line_bot_api.reply_message(tk, reply_arr)
                
                # reply_message(msg[0], tk, os.getenv("CHANNEL_ACCESS_TOKEN"))
                # reply_image(msg[1], tk, os.getenv("CHANNEL_ACCESS_TOKEN"))

        if tp == "location":
            address = json_data["events"][0]["message"]["address"].replace(
                "台", "臺"
            )  # 取出地址資訊，並將「台」換成「臺」
            reply_message(
                f"{address}\n\n{current_weather(address)}",
                tk,
                os.getenv("CHANNEL_ACCESS_TOKEN"),
            )
            print(address)

    except Exception as error:
        print(error)  # 如果發生錯誤，印出收到的內容
    return "OK"


if __name__ == "__main__":
    app.run()
