from flask import Flask, request, jsonify

# 初始化 Flask 應用
app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def linebot():
    if request.method == 'GET':
        return "伺服器正常運作！"

    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    try:
        # 這裡你需要根據實際邏輯處理 body 和 signature
        print(f"接收到的請求體: {body}")

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return 'Internal Server Error', 500

    return 'OK'

# 確保主程式入口
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
