import os
import time
import telebot
from datetime import datetime
from dotenv import load_dotenv
from vnstock.ui import Market


def send_msg(msg):
    print(msg)
    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")


def get_volume(data, column):
    if column not in data.columns:
        return 0
    return int(float(data[column].values[0]))


def build_alert(symbol, kind, delta, limit, timestamp):
    alert_config = {
        "buy": ("🚨", "GOMMM!", "📥", "gom", "🔥"),
        "sell": ("⚠️", "XẢAA!", "📤", "xả", "💥"),
    }
    icon, title, volume_icon, action, ending = alert_config[kind]
    return (
        f"{icon} *[{symbol}] {title}* {icon}\n"
        f"⏱ Thời gian: `{timestamp.strftime('%H:%M:%S')}`\n"
        f"{volume_icon} Lượng {action} trong {INTERVAL_IN_MINUTE} phút: `+{delta:,}` CP > `{limit:,}` CP{ending}\n"
    )


def check_alert(symbol, kind, delta, threshold, timestamp):
    limit = threshold * INTERVAL_IN_MINUTE
    if delta >= limit:
        action = "MUA" if kind == "buy" else "BÁN"
        with open("foreign-log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(
                f"{timestamp:%Y-%m-%d %H:%M:%S} | {symbol} | "
                f"{action} | Khối lượng: {delta:,} CP\n"
            )
        send_msg(build_alert(symbol, kind, delta, limit, timestamp))


def get_current_volumes(data):
    return {
        "buy": get_volume(data, "foreign_buy_volume"),
        "sell": get_volume(data, "foreign_sell_volume"),
        "close_price": get_volume(data, "close_price")
    }

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

DEFAULT_THRESHOLD = 25_000
WATCH_SYMBOL_GROUPS = (
    "STB CTG TCB VPB",  # bank
    "HCM VIX TCX SSI",  # chứng
    "NLG TCH KDH",  # đất
    "GAS BCM GVR",  # Nhà nước
    "FPT MSN DGW VSC",  # Linh tinh
    "VIC GEX",  # Vin, GELEX
)
WATCH_PORTFOLIO = {
    symbol: {"buy_threshold": DEFAULT_THRESHOLD, "sell_threshold": DEFAULT_THRESHOLD}
    for group in WATCH_SYMBOL_GROUPS
    for symbol in group.split()
}

DEFAULT_INTERVAL = 60
INTERVAL = 120
INTERVAL_IN_MINUTE = INTERVAL / DEFAULT_INTERVAL

bot = telebot.TeleBot(TELEGRAM_TOKEN)
mkt = Market()

# Bộ nhớ đệm lưu khối lượng phút trước
last_data = {}

send_msg(f"🚀 Bot đã kích hoạt chế độ canh gác đột biến theo phút cho {len(WATCH_PORTFOLIO)} mã cổ phiếu!")

while True:
    try:
        now = datetime.now()
        # Kiểm tra giờ giao dịch (9h00 - 15h00, Thứ 2 - Thứ 6)
        if now.weekday() < 5 and (9 <= now.hour < 15):
            print('=========', now, '=========')

            for symbol, thresholds in WATCH_PORTFOLIO.items():
                df = mkt.quote(symbol)
                if df is not None and not df.empty:
                    current = get_current_volumes(df)
                    print(
                        symbol,
                        current["close_price"],
                        current["buy"],
                        current["sell"],
                        current["buy"] - current["sell"],
                    )

                    if symbol in last_data:
                        for kind in ("buy", "sell"):
                            delta = current[kind] - last_data[symbol][kind]
                            check_alert(
                                symbol,
                                kind,
                                delta,
                                thresholds[f"{kind}_threshold"],
                                now,
                            )

                    last_data[symbol] = current
                
                time.sleep(1.5)

            print('=========', 'END', '=========')
        time.sleep(INTERVAL)
        
    except Exception as e:
        print(f"Lỗi hệ thống: {e}. Đang thử lại sau 10 giây...")
        time.sleep(10)
