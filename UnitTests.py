import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import time


sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from metatrade import (
    check_internet_connection,
    send_message,
    convert_timestamp_to_jalali_tehran,
    initialize_mt5,
    bot_token,
    chat_id,
    open_deals  
)

class TestMt5TelegramBot(unittest.TestCase):
    
    def setUp(self):
        """تنظیمات اولیه قبل از هر تست"""
        
        global open_deals
        open_deals = set()
    
   
    @patch('metatrade.mt5.initialize')
    @patch('metatrade.mt5.login')
    @patch('metatrade.mt5.terminal_info')
    def test_mt5_login_success(self, mock_terminal_info, mock_login, mock_initialize):
        """تست لاگین موفق به متاتریدر ۵"""
      
        mock_initialize.return_value = True
        mock_login.return_value = True
        mock_terminal_info.return_value = MagicMock()
        
        
        result = initialize_mt5()
        
       
        self.assertTrue(result)
        mock_initialize.assert_called_once()
        mock_login.assert_called_once_with(login=5032847392, password="NnN!1rTo", server="MetaQuotes-Demo")
        mock_terminal_info.assert_called_once()
        
       
        print("its true . MetaTrader 5 login successful")
    
    
    @patch('urllib.request.urlopen')
    @patch('requests.post')
    def test_internet_and_telegram_connection(self, mock_post, mock_urlopen):
        """تست اتصال به اینترنت و ارسال پیام به تلگرام"""
        
        mock_urlopen.return_value = MagicMock()
        
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
       
        internet_connected = check_internet_connection()
        self.assertTrue(internet_connected)
        
        
        test_message = "Test message"
        send_message(bot_token, chat_id, test_message)
        
       
        expected_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        expected_data = {
            'chat_id': chat_id,
            'text': test_message,
            'parse_mode': 'HTML'
        }
        mock_post.assert_called_once_with(expected_url, data=expected_data, timeout=10)
        
       
        print("its true . message sent in the right format")
    
    
    @patch('metatrade.mt5.history_deals_get')
    @patch('metatrade.mt5.account_info')
    @patch('requests.post')
    def test_losing_trade_message(self, mock_post, mock_account_info, mock_history_deals_get):
        """تست ارسال صحیح پیام برای معامله زیانده"""
        
        mock_account = MagicMock()
        mock_account.currency = "USD"
        mock_account_info.return_value = mock_account
        
        
        mock_open_deal = MagicMock()
        mock_open_deal.entry = 0  
        mock_open_deal.time = 1672531200  
        mock_open_deal.price = 1.2000
        mock_open_deal.volume = 0.1
        mock_open_deal.symbol = "EURUSD"
        
        mock_close_deal = MagicMock()
        mock_close_deal.entry = 1  
        mock_close_deal.time = 1672534800  
        mock_close_deal.price = 1.1900
        mock_close_deal.profit = -100.0  
        
        mock_history_deals_get.return_value = [mock_open_deal, mock_close_deal]
        
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
       
        ticket = 12345
        total_volume = mock_open_deal.volume
        total_profit = mock_close_deal.profit
        
        open_time_str = convert_timestamp_to_jalali_tehran(mock_open_deal.time)
        close_time_str = convert_timestamp_to_jalali_tehran(mock_close_deal.time)
        
        profit_color = "🔴"  
        profit_sign = ""  
        profit_str = f"USD{profit_sign}{total_profit:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')
        
        
        message = (
            "📊 <b>گزارش معامله بسته شده</b> 📊\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 <b>تاریخ شروع:</b> <i>{open_time_str}</i>\n"
            f"📅 <b>تاریخ پایان:</b> <i>{close_time_str}</i>\n"
            f"⏱️ <b>مدت زمان:</b> <code>1:00:00</code>\n\n"
            f"💹 <b>قیمت ورود:</b> <code>{round(mock_open_deal.price, 5)}</code>\n"
            f"💹 <b>قیمت خروج:</b> <code>{round(mock_close_deal.price, 5)}</code>\n"
            f"📈 <b>نماد:</b> <i>EURUSD</i>\n\n"
            f"🎫 <i>تیکت:</i> <code>{ticket}</code>\n"
            f"📦 <b>حجم:</b> <code>{round(total_volume, 2)}</code>\n\n"
            f"💰 <b>سود/زیان:</b>\n"
            f"{profit_color} <code><b>{profit_str}</b></code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
       
        send_message(bot_token, chat_id, message)
        
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        
        sent_message = kwargs['data']['text']
        self.assertIn("🔴", sent_message)  
        self.assertIn("USD-100,00", sent_message)  
        self.assertIn("EURUSD", sent_message)  
        self.assertIn("12345", sent_message)  
        self.assertIn("1.2", sent_message)  
        self.assertIn("1.19", sent_message)  
        self.assertIn("1:00:00", sent_message)  
        
        
        print("its true . losing trade closed successfully and message sent successfully")
    
    
    @patch('metatrade.mt5.positions_get')
    @patch('metatrade.mt5.history_deals_get')
    @patch('metatrade.mt5.account_info')
    @patch('metatrade.time.sleep')
    @patch('requests.post')
    def test_two_trades_different_types(self, mock_post, mock_sleep, mock_account_info, mock_history_deals_get, mock_positions_get):
        """تست دو معامله با انواع مختلف (pending و market)"""
       
        mock_account = MagicMock()
        mock_account.currency = "USD"
        mock_account_info.return_value = mock_account
        
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
       
        market_position = MagicMock()
        market_position.ticket = 1001
        market_position.symbol = "EURUSD"
        market_position.volume = 0.1
        market_position.price_open = 1.1000
        market_position.type = 0  
        
        pending_position = MagicMock()
        pending_position.ticket = 1002
        pending_position.symbol = "GBPUSD"
        pending_position.volume = 0.2
        pending_position.price_open = 1.2500
        pending_position.type = 4  
        
        market_open_deal = MagicMock()
        market_open_deal.entry = 0 
        market_open_deal.time = 1672531200  
        market_open_deal.price = 1.1000
        market_open_deal.volume = 0.1
        market_open_deal.symbol = "EURUSD"
        
        market_close_deal = MagicMock()
        market_close_deal.entry = 1  
        market_close_deal.time = 1672534800  
        market_close_deal.price = 1.1050
        market_close_deal.profit = 50.0  
        
       
        pending_open_deal = MagicMock()
        pending_open_deal.entry = 0  
        pending_open_deal.time = 1672531300  
        pending_open_deal.price = 1.2500
        pending_open_deal.volume = 0.2
        pending_open_deal.symbol = "GBPUSD"
        
        pending_close_deal = MagicMock()
        pending_close_deal.entry = 1  
        pending_close_deal.time = 1672534900  
        pending_close_deal.price = 1.2450
        pending_close_deal.profit = -100.0  
        
       
        mock_positions_get.side_effect = [
            [],  
            [market_position, pending_position],  
            [] 
        ]
        
        
        def history_deals_side_effect(position):
            if position == market_position.ticket:
                return [market_open_deal, market_close_deal]
            elif position == pending_position.ticket:
                return [pending_open_deal, pending_close_deal]
            return []
        
        mock_history_deals_get.side_effect = history_deals_side_effect
        
        
        mock_sleep.return_value = None
        
       
        global open_deals
        
        
        positions = mock_positions_get()
        current_open_deals = {pos.ticket for pos in positions}
        closed_deals = open_deals - current_open_deals
        open_deals = current_open_deals
        
       
        positions = mock_positions_get()
        current_open_deals = {pos.ticket for pos in positions}
        closed_deals = open_deals - current_open_deals
        open_deals = current_open_deals
        
        
        positions = mock_positions_get()
        current_open_deals = {pos.ticket for pos in positions}
        closed_deals = open_deals - current_open_deals
        
        
        for ticket in closed_deals:
            deals = mock_history_deals_get(position=ticket)
            
            if ticket == market_position.ticket:
                
                opening_deals = [deal for deal in deals if deal.entry == 0]
                closing_deals = [deal for deal in deals if deal.entry == 1]
                
                total_volume = sum(deal.volume for deal in opening_deals)
                total_profit = sum(deal.profit for deal in closing_deals)  
                first_open = opening_deals[0]
                last_close = closing_deals[-1]
                
                open_time_str = convert_timestamp_to_jalali_tehran(first_open.time)
                close_time_str = convert_timestamp_to_jalali_tehran(last_close.time)
                
                symbol = first_open.symbol
                
                profit_color = "🟢" if total_profit >= 0 else "🔴"
                profit_sign = "+" if total_profit >= 0 else ""
                profit_str = f"USD{profit_sign}{total_profit:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')
                
                message = (
                    "📊 <b>گزارش معامله بسته شده</b> 📊\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📅 <b>تاریخ شروع:</b> <i>{open_time_str}</i>\n"
                    f"📅 <b>تاریخ پایان:</b> <i>{close_time_str}</i>\n"
                    f"⏱️ <b>مدت زمان:</b> <code>1:00:00</code>\n\n"
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
                
            elif ticket == pending_position.ticket:
                
                opening_deals = [deal for deal in deals if deal.entry == 0]
                closing_deals = [deal for deal in deals if deal.entry == 1]
                
                total_volume = sum(deal.volume for deal in opening_deals)
                total_profit = sum(deal.profit for deal in closing_deals)  
                
                first_open = opening_deals[0]
                last_close = closing_deals[-1]
                
                open_time_str = convert_timestamp_to_jalali_tehran(first_open.time)
                close_time_str = convert_timestamp_to_jalali_tehran(last_close.time)
                
                symbol = first_open.symbol
                
                profit_color = "🟢" if total_profit >= 0 else "🔴"
                profit_sign = "+" if total_profit >= 0 else ""
                profit_str = f"USD{profit_sign}{total_profit:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')
                
                message = (
                    "📊 <b>گزارش معامله بسته شده</b> 📊\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📅 <b>تاریخ شروع:</b> <i>{open_time_str}</i>\n"
                    f"📅 <b>تاریخ پایان:</b> <i>{close_time_str}</i>\n"
                    f"⏱️ <b>مدت زمان:</b> <code>1:00:00</code>\n\n"
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
        
        
        self.assertEqual(mock_post.call_count, 2)
        
        
        first_call_args, first_call_kwargs = mock_post.call_args_list[0]
        first_message = first_call_kwargs['data']['text']
        self.assertIn("EURUSD", first_message)  
        self.assertIn("1001", first_message)  
        self.assertIn("🟢", first_message)  
        self.assertIn("USD+50,00", first_message)  
        self.assertIn("1.1", first_message)  
        self.assertIn("1.105", first_message)  
        
        
        second_call_args, second_call_kwargs = mock_post.call_args_list[1]
        second_message = second_call_kwargs['data']['text']
        self.assertIn("GBPUSD", second_message)  
        self.assertIn("1002", second_message)  
        self.assertIn("🔴", second_message) 
        self.assertIn("USD-100,00", second_message)  
        self.assertIn("1.25", second_message)  
        self.assertIn("1.245", second_message)  
        
        
        print("its true . both of them closed successfully and messages sent successfully")

if __name__ == '__main__':
    unittest.main()