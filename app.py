import requests, json
headers = {'Authorization':'1PlQGmb524SP8EccC6ZKIvX47fzf0u9pRZy0E4oCjx71d5gTBTy2U+JzlcfWMc10r4haBWSJHSv7kIE/cnRCnFM6VNtF3CMmTzVAR7n7xtlyiJs3RuuMXhPq+xOv4f9IJontF4iVL8amDiYMJlUxCAdB04t89/1O/w1cDnyilFU=','Content-Type':'application/json'}
body = {
    'replyToken':'ddd4a0b2e26f45278fdda78cd481e6d8',
    'messages':[{
            'type': 'text',
            'text': 'hello'
        }]
}
req = requests.request('POST', 'https://test01-1fbw.onrender.com/callback', headers=headers,data=json.dumps(body).encode('utf-8'))
print(req.text)
