@app.route("/", methods=['GET', 'POST'])
def linebot():
    if request.method == 'GET':
        return "伺服器正常運作！"

    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    try:
        handler.handle(body=body, signature=signature)
        json_data = json.loads(body)
        
        if 'events' in json_data and len(json_data['events']) > 0:
            event = json_data['events'][0]
            print(f"接收到事件: {event}")
        else:
            print("沒有事件需要處理")

    except InvalidSignatureError:
        print("簽名驗證失敗！")
        return 'Invalid Signature', 400
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
        return 'Internal Server Error', 500

    return 'OK'
