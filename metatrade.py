import MetaTrader5 as mt5
import pandas as pd
import requests
import time
import json
from datetime import datetime, timedelta

bot_token = '8263793208:AAHv-D7I97k-T9FC9OTNhQz7bUq1unnpYMA'
chat_id = '-1002470112369'
interval = 10
login = 5032847392
password = "NnN!1rTo"
server = "MetaQuotes-Demo"
open_deals = set()

def send_message(bot_token, chat_id, message):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        print(f"Message sent successfully to channel {chat_id}.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")

# Initialize and login to MT5
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

if not mt5.login(login=login, password=password, server=server):
    print("login() failed, error code =", mt5.last_error())
    mt5.shutdown()
    quit()

print("Successfully logged in to MetaTrader 5 account.")

if mt5.terminal_info() is None:
    print("Failed to connect to MetaTrader 5, check connection and settings.")
    mt5.shutdown()
    quit()

print("Successfully connected to MetaTrader 5.")

while True:
    positions = mt5.positions_get()
    current_open_deals = {pos.ticket for pos in positions}
    closed_deals = open_deals - current_open_deals
    
    if closed_deals:
        for ticket in closed_deals:
            print(f"Position with ticket {ticket} closed. Retrieving history...")
            
          
            time.sleep(3)
            
           
            deals = mt5.history_deals_get(position=ticket)
            
            if deals is None or len(deals) == 0:
                print(f"No deals found for position {ticket}. Error: {mt5.last_error()}")
                message = f"معامله با تیکت {ticket} بسته شد، اما اطلاعات آن در تاریخچه یافت نشد."
                send_message(bot_token, chat_id, message)
                continue
            
            
            opening_deals = [deal for deal in deals if deal.entry == mt5.DEAL_ENTRY_IN]
            closing_deals = [deal for deal in deals if deal.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT)]
            
            if not opening_deals or not closing_deals:
                message = f"خطا در پردازش معاملات پوزیشن {ticket}: معاملات ورودی یا خروجی یافت نشد."
                send_message(bot_token, chat_id, message)
                continue
            
        
            total_volume = sum(deal.volume for deal in opening_deals)
            total_profit = sum(deal.profit for deal in deals)
            
            
            first_open = opening_deals[0]
            last_close = closing_deals[-1]
            
           
            open_time = datetime.fromtimestamp(first_open.time)
            close_time = datetime.fromtimestamp(last_close.time)
            
           
            message = (
                f"تاریخ شروع: {open_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"تاریخ پایان: {close_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"قیمت ورود: {first_open.price}\n"
                f"قیمت خروج: {last_close.price}\n"  # Fixed: Use deal.price for exit price
                f"تیکت: {ticket}\n"
                f"سود: {total_profit}\n"
                f"نماد: {first_open.symbol}\n"
                f"حجم: {total_volume}\n"
            )
            
            send_message(bot_token, chat_id, message)
    
    open_deals = current_open_deals
    time.sleep(interval)

mt5.shutdown()