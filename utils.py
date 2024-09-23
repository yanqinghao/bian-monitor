import os
from datetime import datetime

eth_threshhold = 2740
btc_threshhold = 63900


def format_timestamp(timestamp):
    timestamp = int(timestamp) / 1000
    dt_object = datetime.fromtimestamp(timestamp)
    formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')[
        :-3
    ]  # 保留小数点后三位
    return formatted_time


def load_platform_specific_modules():
    if os.name == 'nt':  # Windows系统
        try:
            import winsound

            return winsound, None
        except ImportError:
            raise ImportError('Failed to load winsound on Windows.')
    elif os.name == 'posix':  # 类Unix系统
        try:
            import curses

            return None, curses
        except ImportError:
            raise ImportError('Failed to load curses on Linux/Unix.')


def play_alert_sound(coin_name, price):
    winsound, curses = load_platform_specific_modules()

    if coin_name == 'ETHUSDT' and float(price) > eth_threshhold:
        alert_action('ETHUSDT', price, winsound, curses)
    elif coin_name == 'BTCUSDT' and float(price) > btc_threshhold:
        alert_action('BTCUSDT', price, winsound, curses)


def alert_action(coin_name, price, winsound, curses):
    if os.name == 'nt' and winsound:  # Windows系统
        winsound.Beep(1000, 500)
    elif os.name == 'posix' and curses:  # 类Unix系统
        # stdscr = curses.initscr()
        # curses.start_color()
        # curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        # stdscr.addstr(
        #     0, 0, f'Alert! {coin_name} price is {price}', curses.color_pair(1)
        # )
        # stdscr.refresh()
        # curses.napms(2000)  # 显示2秒钟
        # curses.endwin()
        pass
