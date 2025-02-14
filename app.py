from flask import Flask, request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
import os

app = Flask(__name__)

# 使用環境變數來存取 LINE API 金鑰
ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
SECRET = os.getenv("LINE_SECRET")

# 初始化 LINE Messaging API
config = Configuration(access_token=ACCESS_TOKEN)
messaging_api = MessagingApi(api_client=ApiClient(configuration=config))
handler = WebhookHandler(channel_secret=SECRET)

@app.route("/", methods=['GET', 'POST'])
def linebot():
    if request.method == 'GET':
        return "伺服器正常運作！"

    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    try:
        handler.handle(body=body, signature=signature)
        print("訊息已接收！")
    except InvalidSignatureError:
        print("簽名驗證失敗！")
        return 'Invalid Signature', 400
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return 'Internal Server Error', 500

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
