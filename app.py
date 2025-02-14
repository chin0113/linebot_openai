from flask import Flask, request
import json
import os

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def linebot():
    if request.method == 'GET':
        return "伺服器正常運作！"

    # 確保變數在函數內部可見
    output_file_path = "output.txt"

    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    try:
        json_data = json.loads(body)

        # 檢查是否有事件
        if 'events' in json_data and len(json_data['events']) > 0:
            event = json_data['events'][0]
            print(f"接收到事件: {event}")

            # 提取 userId 和訊息
            user_id = event['source'].get('userId', '未知使用者')
            message = event['message'].get('text', '空訊息')

            # 將訊息寫入檔案
            with open(output_file_path, "a", encoding="utf-8") as file:
                file.write(f"使用者 ID: {user_id}, 訊息: {message}\n")

            print(f"已將訊息寫入 {output_file_path}")

        else:
            print("沒有事件需要處理")

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return 'Internal Server Error', 500

    return 'OK'

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
