import telegram
import time
import logging
 
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

      
TOKEN = "@firsttt_trybot"
CHAT_ID = "@firsttttry"  
MESSAGE_TEXT = "heloo. this is automatic"
INTERVAL_SECONDS = 60 

def main():
    """تابع اصلی برای راه‌اندازی ربات و ارسال پیام."""
    if TOKEN == "@firsttt_trybot" or CHAT_ID == "@firsttttry":
        logger.error("لطفاً توکن ربات و آیدی کانال را در کد تنظیم کنید!")
        return

    logger.info("ربات شروع به کار کرد. در حال ارسال پیام‌های دوره‌ای...")


    try:
        bot = telegram.Bot(token=TOKEN)
    except Exception as e:
        logger.error(f"خطا در ایجاد نمونه Bot: {e}")
        logger.error("ممکن است توکن ربات شما نامعتبر باشد.")
        return

     
    while True:
        try:
              
            bot.send_message(chat_id=CHAT_ID, text=MESSAGE_TEXT)
            logger.info(f"پیام با موفقیت به {CHAT_ID} ارسال شد.")
        except telegram.Error as e:
  
            logger.error(f"خطا در ارسال پیام به {CHAT_ID}: {e}")
            # اگر توکن اشتباه باشد، بهتر است حلقه را متوقف کنیم
            if "Bot token is invalid" in str(e):
                logger.error("توکن ربات نامعتبر است. ربات متوقف می‌شود.")
                break # خروج از حلقه
            elif "chat not found" in str(e):
                logger.error(f"کانال یا چت با آیدی {CHAT_ID} پیدا نشد. ربات متوقف می‌شود.")
                break
        except Exception as e:
            
            logger.error(f"خطای غیرمنتظره در ارسال پیام: {e}")
            
        time.sleep(INTERVAL_SECONDS)

    logger.info("ربات متوقف شد.")


