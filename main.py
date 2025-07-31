import requests
import time
import json


bot_token = '8263793208:AAHv-D7I97k-T9FC9OTNhQz7bUq1unnpYMA'
chat_id = '-1002470112369'
message = 'this is auto'
interval = 90  

def send_message(bot_token, chat_id, message):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  
        print(f"Message '{message}' sent successfully to channel {chat_id}.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        try:
            print(f"Response content: {response.content.decode()}")
        except:
            print("Could not decode response content")


while True:
    send_message(bot_token, chat_id, message)
    time.sleep(interval)
