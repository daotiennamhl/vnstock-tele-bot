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


def parse_price_alerts(value):
    """Parse PRICE_ALERTS entries as SYMBOL:above|below:PRICE, using thousand VND."""
    price_alerts = {}
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Cấu hình PRICE_ALERTS không hợp lệ: {entry!r}. "
                "Dùng định dạng SYMBOL:above|below:PRICE."
            )

        symbol, direction, price = (part.strip() for part in parts)
        symbol = symbol.upper()
        direction = direction.lower()
        if not symbol or direction not in {"above", "below"}:
            raise ValueError(
                f"Cấu hình PRICE_ALERTS không hợp lệ: {entry!r}. "
                "Hướng phải là above hoặc below."
            )

        try:
            threshold = float(price)
        except ValueError as error:
            raise ValueError(
                f"Giá trong cấu hình PRICE_ALERTS không hợp lệ: {price!r}."
            ) from error
        if threshold <= 0:
            raise ValueError(f"Giá PRICE_ALERTS phải lớn hơn 0: {price!r}.")

        price_alerts.setdefault(symbol, []).append((direction, threshold))

    return price_alerts


def build_alert(alerts, timestamp):
    lines = [
        "🚨 *CẢNH BÁO KHỐI LƯỢNG*",
        f"⏱ Thời gian: `{timestamp.strftime('%H:%M:%S')}`",
    ]
    lines.extend(
        f"`{symbol}` | {action}: `{delta:+,}` | `{price / 1000:,.2f}`"
        for symbol, action, delta, price in alerts
    )
    return "\n".join(lines)


def build_price_alert(alerts, timestamp):
    lines = [
        "📊 *CẢNH BÁO GIÁ CỔ PHIẾU*",
        f"⏱ Thời gian: `{timestamp.strftime('%H:%M:%S')}`",
    ]
    lines.extend(
        f"`{symbol}` | {icon} {label} `{threshold:,.2f}` "
        f"(giá hiện tại: `{current_price:,.2f}`)"
        for symbol, icon, label, threshold, current_price in alerts
    )
    return "\n".join(lines)


def get_current_volumes(data):
    return {
        "buy": get_volume(data, "foreign_buy_volume"),
        "sell": get_volume(data, "foreign_sell_volume"),
        "close_price": get_volume(data, "close_price"),
    }


def evaluate_price_alerts(symbol, current_price, previous_price, rules):
    if previous_price is None:
        return []

    alerts = []
    for direction, threshold in rules:
        crossed_up = direction == "above" and previous_price < threshold <= current_price
        crossed_down = direction == "below" and previous_price > threshold >= current_price
        if crossed_up:
            alerts.append((symbol, "💣", "Tăng qua", threshold, current_price))
        elif crossed_down:
            alerts.append((symbol, "💣", "Giảm qua", threshold, current_price))

    return alerts


def evaluate_symbol_alerts(symbol, current, previous, thresholds):
    if previous is None:
        return []

    alerts = []
    buy_delta = current["buy"] - previous["buy"]
    sell_delta = current["sell"] - previous["sell"]
    buy_limit = thresholds["buy_threshold"] * INTERVAL_IN_MINUTE
    sell_limit = thresholds["sell_threshold"] * INTERVAL_IN_MINUTE

    if buy_delta >= buy_limit:
        alerts.append((symbol, "🟢", buy_delta, current["close_price"]))

    if sell_delta >= sell_limit:
        alerts.append((symbol, "🔻", sell_delta, current["close_price"]))

    return alerts


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WATCH_SYMBOL_GROUPS = (
    ("STB CTG TCB VPB SHB VCB HDB ACB BID MBB VIB MSB HPG", 40_000),  # bank
    ("SSI VIX HCM VND VCI TCX VPX VCK SHS CTS", 20_000),  # chứng
    ("NLG TCH KDH CII NVL DXG DIG CEO PDR HDC", 20_000),  # đất
    ("GAS GVR PLX BVH POW", 20_000),  # Nhà nước
    ("BCM VTP", 3000),
    ("VIC VHM VRE GEX GEE VSC VGC HAH PET", 20_000),  # Vin gex
    ("FPT FRT CMG MSN MCH DGW MWG GMD ANV", 20_000),  # Linh tinh
    ("PVT PVD PVC PVS OIL BSR DPM DCM", 20_000), # Dầu Phân
)

WATCH_PORTFOLIO = {
    symbol: {"buy_threshold": threshold, "sell_threshold": threshold}
    for symbol, threshold in sorted(
        (
            (symbol, threshold)
            for group, threshold in WATCH_SYMBOL_GROUPS
            for symbol in group.split()
        ),
        key=lambda item: item[0],
    )
}
PRICE_ALERTS = parse_price_alerts(os.getenv("PRICE_ALERTS", ""))

START_TRADING_TIME = 9
END_TRADING_TIME = 15
DEFAULT_INTERVAL = 60
INTERVAL = 150
INTERVAL_IN_MINUTE = INTERVAL / DEFAULT_INTERVAL
now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)
mkt = Market()

# Bộ nhớ đệm lưu khối lượng phút trước
last_data = {}

send_msg(f"🚀 Bot đã kích hoạt chế độ canh gác đột biến theo phút cho {len(WATCH_PORTFOLIO)} mã cổ phiếu! {now}")

while True:
    try:
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        if now.hour >= END_TRADING_TIME:
            send_msg(f"[{now.strftime('%H:%M:%S')}] Đã đến khung giờ dừng (15:00). Tiến hành tắt app hoàn toàn...")
            sys.exit(0)

        if now.weekday() < 5 and (START_TRADING_TIME <= now.hour < END_TRADING_TIME):
            print(f"========= {now} =========")
            alerts = []
            price_alerts = []
            symbols = sorted(set(WATCH_PORTFOLIO) | set(PRICE_ALERTS))
            df = mkt.quote(symbols)

            if df is None or df.empty:
                print("[INFO] Không có dữ liệu quote trong vòng lặp hiện tại.")
            else:
                for symbol in symbols:
                    symbol_data = df[df["symbol"] == symbol]
                    if symbol_data.empty:
                        continue

                    current = get_current_volumes(symbol_data)
                    previous = last_data.get(symbol)
                    if symbol in WATCH_PORTFOLIO:
                        print(
                            f'{symbol} | Price: {current["close_price"] / 1000:,.2f} | '
                            f'Buy: {current["buy"]:,} | '
                            f'Sell: {current["sell"]:,} | '
                            f'Net: {current["buy"] - current["sell"]:+,}'
                        )
                        alerts.extend(
                            evaluate_symbol_alerts(
                                symbol, current, previous, WATCH_PORTFOLIO[symbol]
                            )
                        )

                    price_alerts.extend(
                        evaluate_price_alerts(
                            symbol,
                            current["close_price"] / 1000,
                            previous["close_price"] / 1000 if previous else None,
                            PRICE_ALERTS.get(symbol, []),
                        )
                    )
                    last_data[symbol] = current

            print("========= END =========")
            if alerts:
                send_msg(build_alert(alerts, now))
            if price_alerts:
                send_msg(build_price_alert(price_alerts, now))

        time.sleep(INTERVAL)

    except Exception as e:
        print(f"Lỗi hệ thống: {e}. Đang thử lại sau 10 giây...")
        time.sleep(10)
