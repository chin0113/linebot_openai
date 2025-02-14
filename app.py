import os

@app.route("/", methods=['GET', 'POST'])
def linebot():
    if request.method == 'GET':
        return "伺服器正常運作！"

    body = request.get_data(as_text=True)
    signature = request.headers.get('X-Line-Signature')

    # 檢查 Excel 檔案是否存在
    excel_path = '/opt/render/Downloads/行雲流水/output_heroku.xlsx'
    id_file_path = '/opt/render/Downloads/行雲流水/id.xlsx'

    if not os.path.exists(excel_path):
        print(f"警告: 檔案 {excel_path} 不存在，跳過初始化 Excel。")

    if not os.path.exists(id_file_path):
        print(f"警告: 檔案 {id_file_path} 不存在，跳過載入 id.xlsx。")

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
