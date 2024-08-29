import curses
import asyncio
import threading
from collections import deque
from websocket_listener import listen_to_stream


class CryptoTop:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.loop = asyncio.new_event_loop()
        self.tasks = []
        self.proxy_url = 'http://10.33.58.241:1081'
        self.base_streams = ['ethusdt@', 'btcusdt@']
        self.stream_options = [
            'aggTrade',
            'kline_1m',
            'kline_5m',
            'kline_15m',
            'kline_1h',
            'kline_4h',
        ]
        self.selected_stream = 'kline_1m'
        self.streams = [
            f'{i}{self.selected_stream}' for i in self.base_streams
        ]
        self.font_size = 10
        self.bg_color = 'black'
        self.history_len = 100
        self.history_price = {
            'BTCUSDT': deque(maxlen=self.history_len),
            'ETHUSDT': deque(maxlen=self.history_len),
        }
        self.asyncio_thread = None
        self.start_asyncio_thread()

        # Initialize UI
        self.setup_ui(stdscr)

    def start_asyncio_thread(self):
        # 如果已有线程在运行，先停止它
        if self.asyncio_thread and self.asyncio_thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.asyncio_thread.join()

        # 创建并启动新的 asyncio 事件循环线程
        self.asyncio_thread = threading.Thread(
            target=self.run_asyncio_loop, daemon=True
        )
        self.asyncio_thread.start()

    def setup_ui(self, stdscr):
        curses.curs_set(0)  # 隐藏光标
        stdscr.clear()
        stdscr.refresh()

        # 初始化窗口布局
        self.height, self.width = stdscr.getmaxyx()

        # 分割窗口区域
        self.price_win = curses.newwin(self.height - 6, self.width, 0, 0)
        self.settings_win = curses.newwin(6, self.width, self.height - 6, 0)

        # 绘制初始界面
        self.draw_price_tab()
        self.draw_settings_tab()

    def draw_price_tab(self):
        self.price_win.clear()
        self.price_win.border(0)

        # 标题
        self.price_win.addstr(1, 2, 'Crypto Alert Terminal', curses.A_BOLD)
        self.price_win.addstr(2, 2, '=' * (self.width - 4))

        # 显示当前数据
        self.update_data_display()

        self.price_win.refresh()

    def update_data_display(self):
        btc_line = f"BTC: Time: {self.history_price['BTCUSDT'][-1]['time'] if self.history_price['BTCUSDT'] else 'N/A'} Price: {self.history_price['BTCUSDT'][-1]['price'] if self.history_price['BTCUSDT'] else 'N/A'} Trend: {self.history_price['BTCUSDT'][-1]['trend'] if self.history_price['BTCUSDT'] else 'N/A'}"
        eth_line = f"ETH: Time: {self.history_price['ETHUSDT'][-1]['time'] if self.history_price['ETHUSDT'] else 'N/A'} Price: {self.history_price['ETHUSDT'][-1]['price'] if self.history_price['ETHUSDT'] else 'N/A'} Trend: {self.history_price['ETHUSDT'][-1]['trend'] if self.history_price['ETHUSDT'] else 'N/A'}"

        self.price_win.addstr(4, 2, btc_line)
        self.price_win.addstr(5, 2, eth_line)

        self.price_win.refresh()

    def update_data(self, name, time, price, trend, price_close=None):
        # 更新历史记录
        self.history_price[name].append(
            {
                'time': time,
                'price': price,
                'trend': trend,
                'price_close': price_close,
            }
        )
        self.update_data_display()

    def draw_settings_tab(self):
        self.settings_win.clear()
        self.settings_win.border(0)

        # 菜单项
        self.settings_win.addstr(1, 2, 'Press "c" to change background color')
        self.settings_win.addstr(2, 2, 'Press "f" to change font size')
        self.settings_win.addstr(3, 2, 'Press "p" to change proxy URL')
        self.settings_win.addstr(4, 2, 'Press "m" to change memory length')
        self.settings_win.addstr(5, 2, 'Press "s" to change stream type')

        self.settings_win.refresh()

    def show_input_screen(self, prompt):
        """显示输入界面"""
        self.settings_win.clear()
        self.settings_win.border(0)
        self.settings_win.addstr(2, 2, prompt, curses.A_BOLD)
        self.settings_win.refresh()

        curses.echo()
        input_value = self.settings_win.getstr(3, 2).decode('utf-8')
        curses.noecho()

        return input_value

    def change_bg_color(self):
        self.settings_win.addstr(
            1, 2, 'Changing background color is not supported', curses.A_BLINK
        )
        self.settings_win.refresh()
        self.return_to_main_screen()

    def change_font_size(self):
        input_size = self.show_input_screen('Enter new font size (6-20):')
        try:
            new_size = int(input_size)
            if 6 <= new_size <= 20:
                self.font_size = new_size
                self.settings_win.addstr(
                    1, 2, f'Font size changed to {new_size}'
                )
            else:
                self.settings_win.addstr(
                    1, 2, 'Invalid font size, must be between 6 and 20'
                )
        except ValueError:
            self.settings_win.addstr(
                1, 2, 'Invalid input, font size must be a number'
            )

        self.return_to_main_screen()

    def change_proxy(self):
        new_proxy = self.show_input_screen('Enter new proxy URL:')
        if new_proxy:
            self.proxy_url = new_proxy
            self.restart_websockets()
            self.settings_win.addstr(1, 2, f'Proxy URL changed to {new_proxy}')

        self.return_to_main_screen()

    def change_history(self):
        new_len = self.show_input_screen('Enter new history length:')
        try:
            new_len = int(new_len)
            self.history_len = new_len
            self.history_price = {
                'BTCUSDT': deque(maxlen=self.history_len),
                'ETHUSDT': deque(maxlen=self.history_len),
            }
            self.settings_win.addstr(
                1, 2, f'History length changed to {new_len}'
            )
        except ValueError:
            self.settings_win.addstr(
                1, 2, 'Invalid input, history length must be a number'
            )

        self.return_to_main_screen()

    def change_stream(self):
        new_stream = self.show_input_screen('Select new stream type:')
        if new_stream in self.stream_options:
            self.selected_stream = new_stream
            self.streams = [
                f'{i}{self.selected_stream}' for i in self.base_streams
            ]
            self.history_price = {
                'BTCUSDT': deque(maxlen=self.history_len),
                'ETHUSDT': deque(maxlen=self.history_len),
            }
            self.restart_websockets()
            self.settings_win.addstr(
                1, 2, f'Stream type changed to {new_stream}'
            )
        else:
            self.settings_win.addstr(
                1, 2, f'Invalid stream type: {new_stream}'
            )

        self.return_to_main_screen()

    def return_to_main_screen(self):
        """返回初始界面"""
        self.draw_price_tab()
        self.draw_settings_tab()

    def set_window_icon(self, icon_path):
        # 不支持图标设置，在终端模式下忽略
        pass

    def run_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.start_streams())
        self.loop.run_forever()  # 持续运行事件循环

    def run(self):
        while True:
            # 保留这个空循环以保持UI更新
            pass

    def cleanup(self):
        future = asyncio.run_coroutine_threadsafe(
            self.cancel_tasks(), self.loop
        )
        try:
            future.result()
        except Exception as e:
            self.show_error_message(
                'websocket', f'Error during task cancellation: {e}'
            )
        self.loop.call_soon_threadsafe(self.loop.stop)
        curses.endwin()
        if self.asyncio_thread:
            self.asyncio_thread.join()

    def restart_websockets(self):
        future = asyncio.run_coroutine_threadsafe(
            self.cancel_tasks(), self.loop
        )
        try:
            future.result()
        except Exception as e:
            self.show_error_message(
                'websocket', f'Error during task cancellation: {e}'
            )

        self.start_asyncio_thread()

    async def cancel_tasks(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.wait(self.tasks, return_when=asyncio.ALL_COMPLETED)
        self.tasks.clear()
        print('all task canceled')

    async def start_streams(self):
        tasks = []
        for stream_name in self.streams:
            stream_url = f'wss://fstream.binance.com/ws/{stream_name}'
            task = asyncio.create_task(
                listen_to_stream(stream_url, self.proxy_url, self)
            )
            tasks.append(task)
            self.tasks.append(task)

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.show_error_message('task', f'Tasks exist with error: {e}')
