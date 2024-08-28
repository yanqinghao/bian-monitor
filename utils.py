from datetime import datetime
import winsound

eth_threshhold = 2740
btc_threshhold = 63900


def format_timestamp(timestamp):
    timestamp = int(timestamp) / 1000
    dt_object = datetime.fromtimestamp(timestamp)
    formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')[
        :-3
    ]  # 保留小数点后三位
    return formatted_time


def play_alert_sound(coin_name, price):
    if coin_name == 'ETHUSDT' and float(price) > eth_threshhold:
        winsound.Beep(1000, 500)
    elif coin_name == 'BTCUSDT' and float(price) > btc_threshhold:
        winsound.Beep(1000, 500)
