import MetaTrader5 as mt5
import pandas as pd
import requests
import time
import json
from datetime import datetime, timedelta
import html

bot_token = '8263793208:AAHv-D7I97k-T9FC9OTNhQz7bUq1unnpYMA'
chat_id = '-1002470112369'
interval = 5
login = 5032847392
password = "NnN!1rTo"
server = "MetaQuotes-Demo"
open_deals = set()


account_info = mt5.account_info()
account_currency = account_info.currency if account_info else ""

def send_message(bot_token, chat_id, message):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        print(f"Message sent successfully to channel {chat_id}.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")


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
                message = (
                    "⚠️ <b>خطا در بازیابی اطلاعات</b> ⚠️\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"معامله با تیکت <code>{ticket}</code> بسته شد\n"
                    "اما اطلاعات آن در تاریخچه یافت نشد\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                send_message(bot_token, chat_id, message)
                continue
            
            opening_deals = [deal for deal in deals if deal.entry == mt5.DEAL_ENTRY_IN]
            closing_deals = [deal for deal in deals if deal.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT)]
            
            if not opening_deals or not closing_deals:
                message = (
                    "⚠️ <b>خطا در پردازش معامله</b> ⚠️\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"پوزیشن <code>{ticket}</code> دارای ساختار نامعتبر است\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                send_message(bot_token, chat_id, message)
                continue
            
            total_volume = sum(deal.volume for deal in opening_deals)
            total_profit = sum(deal.profit for deal in deals)
            
            first_open = opening_deals[0]
            last_close = closing_deals[-1]
            
            open_time = datetime.fromtimestamp(first_open.time)
            close_time = datetime.fromtimestamp(last_close.time)
            
            symbol = html.escape(first_open.symbol)
            
            
            profit_color = "🟢" if total_profit >= 0 else "🔴"
            profit_sign = "+" if total_profit >= 0 else ""
            profit_str = f"{account_currency}{profit_sign}{total_profit:,.2f}"
            
           
            duration = close_time - open_time
            duration_str = str(duration).split('.')[0]  
            
            
            message = (
                "📊 <b>گزارش معامله بسته شده</b> 📊\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"📅 <b>تاریخ شروع:</b> <i>{open_time.strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
                f"📅 <b>تاریخ پایان:</b> <i>{close_time.strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
                f"⏱️ <b>مدت زمان:</b> <code>{duration_str}</code>\n\n"
                
                f"💹 <b>قیمت ورود:</b> <code>{round(first_open.price, 5)}</code>\n"
                f"💹 <b>قیمت خروج:</b> <code>{round(last_close.price, 5)}</code>\n"
                f"📈 <b>نماد:</b> <i>{symbol}</i>\n\n"
                
                f"🎫 <i>تیکت:</i> <code>{ticket}</code>\n"
                f"📦 <b>حجم:</b> <code>{round(total_volume, 2)}</code>\n\n"
                
                f"💰 <b>سود/زیان:</b>\n"
                f"{profit_color} <code><b>{profit_str}</b></code>\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                
            )
            
            send_message(bot_token, chat_id, message)
    
    open_deals = current_open_deals
    time.sleep(interval)

mt5.shutdown()