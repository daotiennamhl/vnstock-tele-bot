import os
import time
import telebot
from datetime import datetime
from dotenv import load_dotenv
from vnstock.ui import Market
from zoneinfo import ZoneInfo
import sys

def send_msg(msg):
    print(msg)
    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")


def get_volume(data, column):
    if column not in data.columns:
        return 0
    return int(float(data[column].values[0]))


def build_alert(alerts, timestamp):
    lines = [
        "🚨 *CẢNH BÁO KHỐI LƯỢNG*",
        f"⏱ Thời gian: `{timestamp.strftime('%H:%M:%S')}`",
    ]
    lines.extend(
        f"`{symbol}` | {action}: `{delta:+,}` CP"
        for symbol, action, delta in alerts
    )
    return "\n".join(lines)


def get_current_volumes(data):
    return {
        "buy": get_volume(data, "foreign_buy_volume"),
        "sell": get_volume(data, "foreign_sell_volume"),
        "close_price": get_volume(data, "close_price")
    }

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WATCH_SYMBOL_GROUPS = (
    ("STB CTG TCB VPB SHB VCB HDB ACB", 40_000),  # bank
    ("SSI VIX HCM VND VCI TCX VPX VCK", 20_000),  # chứng
    ("NLG TCH KDH CII NVL DXG", 20_000),  # đất
    ("GAS BCM GVR", 20_000),  # Nhà nước
    ("FPT MSN DGW VSC MCH BSR", 20_000),  # Linh tinh
    ("VIC VHM GEX", 20_000),  # Vin
)

WATCH_PORTFOLIO = {
    symbol: {"buy_threshold": threshold, "sell_threshold": threshold}
    for group, threshold in WATCH_SYMBOL_GROUPS
    for symbol in group.split()
}

START_TRADING_TIME = 9
END_TRADING_TIME = 15
DEFAULT_INTERVAL = 60
INTERVAL = 150
INTERVAL_IN_MINUTE = INTERVAL / DEFAULT_INTERVAL

bot = telebot.TeleBot(TELEGRAM_TOKEN)
mkt = Market()

# Bộ nhớ đệm lưu khối lượng phút trước
last_data = {}

send_msg(f"🚀 Bot đã kích hoạt chế độ canh gác đột biến theo phút cho {len(WATCH_PORTFOLIO)} mã cổ phiếu!")

while True:
    try:
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        # Kiểm tra giờ giao dịch (9h00 - 15h00, Thứ 2 - Thứ 6)
        if (now.hour >= END_TRADING_TIME):
            send_msg(f"[{now.strftime('%H:%M:%S')}] Đã đến khung giờ dừng (15:00). Tiến hành tắt app hoàn toàn...")
            sys.exit(0)

        if now.weekday() < 5 and (START_TRADING_TIME <= now.hour < END_TRADING_TIME):
            print('=========', now, '=========')
            alerts = []
            symbols = list(WATCH_PORTFOLIO)
            df = mkt.quote(symbols)

            for symbol, thresholds in WATCH_PORTFOLIO.items():
                symbol_data = df[df["symbol"] == symbol] if df is not None and not df.empty else None
                if symbol_data is not None and not symbol_data.empty:
                    current = get_current_volumes(symbol_data)
                    print(
                        symbol,
                        current["close_price"],
                        current["buy"],
                        current["sell"],
                        current["buy"] - current["sell"],
                    )

                    if symbol in last_data:
                        buy_delta = current["buy"] - last_data[symbol]["buy"]
                        sell_delta = current["sell"] - last_data[symbol]["sell"]
                        buy_limit = thresholds["buy_threshold"] * INTERVAL_IN_MINUTE
                        sell_limit = thresholds["sell_threshold"] * INTERVAL_IN_MINUTE
                        if buy_delta >= buy_limit:
                            alerts.append((symbol, "🟢", buy_delta))
                        if sell_delta >= sell_limit:
                            alerts.append((symbol, "🔻", sell_delta))

                    last_data[symbol] = current

            print('=========', 'END', '=========')
            if alerts:
                send_msg(build_alert(alerts, now))
        time.sleep(INTERVAL)
        
    except Exception as e:
        print(f"Lỗi hệ thống: {e}. Đang thử lại sau 10 giây...")
        time.sleep(10)
