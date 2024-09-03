import curses
import time
import requests
from candlestick_chart import Candle, Chart
from dataclasses import dataclass
import asyncio
import threading
from collections import deque
from websocket_listener import listen_to_stream


@dataclass(frozen=True, slots=True)
class BinanceKlinesItem:
    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int
    quote_asset_volume: str
    number_of_trades: int
    taker_buy_base_asset_volume: str
    taker_buy_quote_asset_volume: str
    ignore: str


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
        self.symbols = [
            'BTCUSDT',
            'ETHUSDT',
        ]
        self.symbol = 'BTCUSDT'
        self.candles_limit = 1000
        self.interval = '15m'
        self.candles = deque(maxlen=self.candles_limit)
        self.last_drawn_candle_time = None
        self.chart = None
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
        self.running = True
        self.start_asyncio_thread()

        # Initialize UI
        self.setup_ui(stdscr)

    def start_asyncio_thread(self):
        if self.asyncio_thread and self.asyncio_thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.asyncio_thread.join()

        self.asyncio_thread = threading.Thread(
            target=self.run_asyncio_loop, daemon=True
        )
        self.asyncio_thread.start()

    def start_candle_asyncio_thread(self):
        if self.asyncio_thread and self.asyncio_thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.asyncio_thread.join()

        self.asyncio_thread = threading.Thread(
            target=self.run_candle_asyncio_loop, daemon=True
        )
        self.asyncio_thread.start()

    def setup_ui(self, stdscr):
        curses.curs_set(0)
        stdscr.clear()
        stdscr.refresh()

        self.price_win = curses.newwin(7, 110, 0, 0)
        self.settings_win = curses.newwin(7, 110, 7, 0)

        self.draw_price_tab()
        self.draw_settings_tab()

    def draw_price_tab(self):
        self.price_win.clear()
        self.price_win.border(0)

        self.price_win.addstr(1, 2, 'Crypto Alert Terminal', curses.A_BOLD)
        self.price_win.addstr(2, 2, '=' * (110 - 4))

        self.update_data_display()

        self.price_win.refresh()

    def update_data_display(self):
        btc_line = f"BTC: Time: {self.history_price['BTCUSDT'][-1]['time'] if self.history_price['BTCUSDT'] else 'N/A'} Price: {self.history_price['BTCUSDT'][-1]['price'] if self.history_price['BTCUSDT'] else 'N/A'} Trend: {self.history_price['BTCUSDT'][-1]['trend'] if self.history_price['BTCUSDT'] else 'N/A'}"
        eth_line = f"ETH: Time: {self.history_price['ETHUSDT'][-1]['time'] if self.history_price['ETHUSDT'] else 'N/A'} Price: {self.history_price['ETHUSDT'][-1]['price'] if self.history_price['ETHUSDT'] else 'N/A'} Trend: {self.history_price['ETHUSDT'][-1]['trend'] if self.history_price['ETHUSDT'] else 'N/A'}"

        self.price_win.addstr(4, 2, btc_line)
        self.price_win.addstr(5, 2, eth_line)

        self.price_win.refresh()

    def update_data(self, name, time, price, trend, price_close=None):
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

        self.settings_win.addstr(1, 2, 'Press "c" to check candlestick chart')
        self.settings_win.addstr(2, 2, 'Press "f" to change font size')
        self.settings_win.addstr(3, 2, 'Press "p" to change proxy URL')
        self.settings_win.addstr(4, 2, 'Press "m" to change memory length')
        self.settings_win.addstr(5, 2, 'Press "s" to change stream type')

        self.settings_win.refresh()

    def show_input_screen(self, prompt):
        self.settings_win.clear()
        self.settings_win.border(0)
        self.settings_win.addstr(2, 2, prompt, curses.A_BOLD)
        self.settings_win.refresh()

        curses.echo()
        input_value = self.settings_win.getstr(3, 2).decode('utf-8')
        curses.noecho()

        return input_value

    def fetch_candlestick_data(self, symbol, interval, limit):
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}'
        with requests.get(url) as req:
            klines = [BinanceKlinesItem(*item) for item in req.json()]

        candles = [
            Candle(
                open=kline.open,
                close=kline.close,
                high=kline.high,
                low=kline.low,
                volume=kline.volume,
                timestamp=kline.open_time,
            )
            for kline in klines
        ]

        return candles

    def update_candlestick_chart(self, candle: Candle):
        if candle.timestamp in [c.timestamp for c in self.candles]:
            self.candles.pop()
        else:
            self.candles = self.candles[-self.candles_limit :]
        self.candles.append(candle)

        # # Clear the current screen
        # self.stdscr.clear()
        if time.time() - self.last_drawn_candle_time > 3:
            curses.curs_set(0)  # 隐藏光标
            curses.endwin()
            # self.stdscr.clear()  # Clear the screen to display the chart
            self.chart.update_candles(self.candles, reset=True)
            self.chart.draw()
        # Refresh the screen to display the changes
        # self.stdscr.refresh()

    def plot_candlestick_chart(self):
        symbol = self.show_input_screen(
            'Enter symbol (e.g., BTCUSDT(1) or ETHUSDT(2), or others):'
        )
        if symbol == '1':
            symbol = 'BTCUSDT'
        elif symbol == '2':
            symbol = 'ETHUSDT'
        elif symbol == '':
            symbol = 'BTCUSDT'
        self.symbol = symbol
        interval = self.show_input_screen('Enter interval (e.g., 15m):')
        if interval == '':
            interval = '15m'
        self.interval = interval
        limit = self.show_input_screen('Enter limit (e.g., 96):')
        if limit == '':
            limit = 96
        self.candles_limit = int(limit)
        future = asyncio.run_coroutine_threadsafe(
            self.cancel_tasks(), self.loop
        )
        try:
            future.result()
        except Exception as e:
            self.show_error_message(
                'websocket', f'Error during task cancellation: {e}'
            )
        self.history_price = {
            'BTCUSDT': deque(maxlen=self.history_len),
            'ETHUSDT': deque(maxlen=self.history_len),
        }

        try:
            candles = self.fetch_candlestick_data(
                self.symbol, interval, self.candles_limit
            )
            self.candles = candles
            # Exit curses before plotting the chart
            curses.curs_set(0)  # 隐藏光标
            curses.endwin()
            # self.stdscr = curses.initscr()
            # curses.curs_set(0)  # Hide cursor
            # self.stdscr.clear()  # Clear the screen to display the chart
            self.chart = Chart(
                self.candles, title=f'{symbol.upper()} Candlestick Chart'
            )

            self.chart.set_bull_color(1, 205, 254)
            self.chart.set_bear_color(255, 107, 153)
            self.chart.set_volume_pane_height(4)
            self.chart.set_volume_pane_enabled(True)
            self.chart.draw()

            self.last_drawn_candle_time = time.time()

            self.start_candle_asyncio_thread()

            self.show_return_prompt()

        except Exception as e:
            self.settings_win.addstr(1, 2, f'Error: {e}', curses.A_BLINK)
            self.settings_win.refresh()
            self.candles_limit = 1000
            self.candles = deque(maxlen=self.candles_limit)
            self.return_to_main_screen()
        finally:
            # Restart curses after plotting
            self.stdscr = curses.initscr()
            curses.curs_set(0)  # Hide cursor
            self.setup_ui(self.stdscr)
            self.start_asyncio_thread()

    def show_return_prompt(self):
        # self.stdscr.addstr(1, 2, 'Press "r" to return to the main screen')
        # self.stdscr.refresh()
        while True:
            key = self.stdscr.getch()
            if key == ord('r'):
                self.candles_limit = 1000
                self.candles = deque(maxlen=self.candles_limit)
                future = asyncio.run_coroutine_threadsafe(
                    self.cancel_tasks(), self.loop
                )
                try:
                    future.result()
                except Exception as e:
                    self.show_error_message(
                        'websocket', f'Error during task cancellation: {e}'
                    )
                self.return_to_main_screen()
                break

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
        self.stdscr.clear()
        self.setup_ui(self.stdscr)

    def run_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.start_streams())
        self.loop.run_forever()

    def run_candle_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.start_candle_listener())
        self.loop.run_forever()

    def run(self):
        while self.running:  # 检查运行标志
            pass

    def cleanup(self):
        self.running = False
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
        self.history_price = {
            'BTCUSDT': deque(maxlen=self.history_len),
            'ETHUSDT': deque(maxlen=self.history_len),
        }
        self.start_asyncio_thread()

    async def cancel_tasks(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.wait(self.tasks, return_when=asyncio.ALL_COMPLETED)
        self.tasks.clear()

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

    async def start_candle_listener(self):
        stream_url = f'wss://fstream.binance.com/ws/{self.symbol.lower()}@kline_{self.interval}'
        task = asyncio.create_task(
            listen_to_stream(stream_url, self.proxy_url, self, is_candle=True)
        )
        self.tasks.append(task)

        try:
            await asyncio.gather(*self.tasks)
        except Exception as e:
            self.show_error_message('task', f'Tasks exist with error: {e}')
