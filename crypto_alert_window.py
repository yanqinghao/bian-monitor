import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
from tkinter import colorchooser, simpledialog
from PIL import Image, ImageTk
import asyncio
import threading
from collections import deque
from tkinter import messagebox
from websocket_listener import listen_to_stream


class CryptoAlertWindow:
    def __init__(self, root, loop):
        self.root = root
        self.loop = loop
        self.tasks = []
        self.proxy_url = 'http://localhost:1081'
        self.base_streams = ['ethusdt@', 'btcusdt@']
        self.stream_options = [
            'aggTrade',
            'kline_1m',
            'kline_5m',
            'kline_15m',
            'kline_1h',
            'kline_4h',
        ]
        self.selected_stream = tk.StringVar(value=self.stream_options[1])
        self.streams = [
            f'{i}{self.selected_stream.get()}' for i in self.base_streams
        ]
        self.font_size = 10
        self.bg_color = 'black'
        self.history_len = 100
        self.history_price = {
            'BTCUSDT': deque(maxlen=self.history_len),
            'ETHUSDT': deque(maxlen=self.history_len),
        }
        self.always_on_top = tk.BooleanVar(
            value=True
        )  # Variable for topmost option
        self.setup_ui()
        self.asyncio_thread = None
        self.start_asyncio_thread()

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

    def toggle_always_on_top(self):
        self.root.attributes('-topmost', self.always_on_top.get())

    def setup_ui(self):
        self.root.title('Crypto Alert')
        self.root.geometry('600x100')
        self.root.attributes(
            '-topmost', self.always_on_top.get()
        )  # Set initial topmost state
        # self.root.attributes('-topmost', True)
        self.root.configure(bg=self.bg_color)
        self.custom_font = tkFont.Font(
            family='Arial', size=self.font_size, weight='bold'
        )
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

        self.set_window_icon('BTC.png')
        self.tab_control = ttk.Notebook(self.root)
        self.create_price_tab()
        self.create_settings_tab()
        self.tab_control.pack(expand=1, fill='both')

    def change_bg_color(self):
        new_color = colorchooser.askcolor(title='Choose Background Color')[1]
        if new_color:
            self.root.configure(bg=new_color)
            self.frame_btc.configure(bg=new_color)
            self.frame_eth.configure(bg=new_color)
            self.label_btc_title.configure(bg=new_color)
            self.label_btc_time.configure(bg=new_color)
            self.label_btc_price.configure(bg=new_color)
            self.label_btc_trend.configure(bg=new_color)
            self.label_eth_title.configure(bg=new_color)
            self.label_eth_time.configure(bg=new_color)
            self.label_eth_price.configure(bg=new_color)
            self.label_eth_trend.configure(bg=new_color)

    def update_data(self, name, time, price, trend, price_close=None):
        self.history_price[name].append(
            {
                'time': time,
                'price': price,
                'trend': trend,
                'price_close': price_close,
            }
        )
        if name == 'BTCUSDT':
            self.label_btc_time.config(text=f'Time: {time}')
            self.label_btc_price.config(text=f'Price: {price}')
            self.label_btc_trend.config(text=f'Trend: {trend}')
        elif name == 'ETHUSDT':
            self.label_eth_time.config(text=f'Time: {time}')
            self.label_eth_price.config(text=f'Price: {price}')
            self.label_eth_trend.config(text=f'Trend: {trend}')
        self.root.update_idletasks()

    def change_font_size(self):
        new_size = simpledialog.askinteger(
            'Input',
            'Enter new font size:',
            minvalue=6,
            maxvalue=20,
            initialvalue=self.font_size,
        )
        if new_size:
            self.font_size = new_size
            self.custom_font.configure(size=new_size)

    def show_info_message(self, title, message):
        messagebox.showinfo(title, message)

    def show_warn_message(self, title, message):
        messagebox.showwarning(title, message)

    def show_error_message(self, title, message):
        messagebox.showerror(title, message)

    def change_proxy(self):
        new_proxy = simpledialog.askstring(
            'Set Proxy',
            'Enter new proxy URL (e.g., http://localhost:1081):',
            initialvalue=self.proxy_url,
        )
        if new_proxy:
            self.proxy_url = new_proxy
            self.restart_websockets()
            self.show_info_message('proxy', 'connect to proxy sucessfully')

    def change_history(self):
        new_history_len = simpledialog.askstring(
            'Set Memory Len',
            'Enter new Memory Len:',
            initialvalue=self.history_len,
        )
        if new_history_len:
            try:
                self.history_len = int(new_history_len)
                self.history_price = {
                    'BTCUSDT': deque(maxlen=self.history_len),
                    'ETHUSDT': deque(maxlen=self.history_len),
                }
                self.show_info_message(
                    'history_len', 'history_len update sucessfully'
                )
            except:
                self.show_info_message(
                    'history_len', 'history_len update failed'
                )

    def change_stream(self, event=None):
        self.streams = [
            f'{i}{self.selected_stream.get()}' for i in self.base_streams
        ]
        self.restart_websockets()
        self.show_info_message(
            'streams',
            f'connect to streams {self.selected_stream.get()} sucessfully',
        )

    def create_scrollable_frame(self, parent):
        canvas = tk.Canvas(parent, bg='black')
        scrollbar = ttk.Scrollbar(
            parent, orient='vertical', command=canvas.yview
        )
        scrollable_frame = ttk.Frame(canvas, style='Custom.TFrame')

        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        return scrollable_frame

    def create_price_tab(self):
        price_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(price_tab, text='Prices')

        scrollable_frame = self.create_scrollable_frame(price_tab)

        self.frame_btc = tk.Frame(scrollable_frame, bg='black')
        self.frame_eth = tk.Frame(scrollable_frame, bg='black')

        self.frame_btc.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.frame_eth.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # BTC 显示区域
        self.label_btc_title = tk.Label(
            self.frame_btc,
            text='BTC',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_btc_title.pack(side=tk.LEFT)
        self.label_btc_time = tk.Label(
            self.frame_btc,
            text='Time: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_btc_time.pack(side=tk.LEFT, padx=5)
        self.label_btc_price = tk.Label(
            self.frame_btc,
            text='Price: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_btc_price.pack(side=tk.LEFT, padx=5)
        self.label_btc_trend = tk.Label(
            self.frame_btc,
            text='Trend: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_btc_trend.pack(side=tk.LEFT, padx=5)

        # ETH 显示区域
        self.label_eth_title = tk.Label(
            self.frame_eth,
            text='ETH',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_eth_title.pack(side=tk.LEFT)
        self.label_eth_time = tk.Label(
            self.frame_eth,
            text='Time: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_eth_time.pack(side=tk.LEFT, padx=5)
        self.label_eth_price = tk.Label(
            self.frame_eth,
            text='Price: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_eth_price.pack(side=tk.LEFT, padx=5)
        self.label_eth_trend = tk.Label(
            self.frame_eth,
            text='Trend: ',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        self.label_eth_trend.pack(side=tk.LEFT, padx=5)

    def create_settings_tab(self):
        settings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(settings_tab, text='Settings')

        scrollable_frame = self.create_scrollable_frame(settings_tab)

        bg_color_button = tk.Button(
            scrollable_frame,
            text='Set Background Color',
            command=self.change_bg_color,
        )
        bg_color_button.pack(pady=10, padx=10, anchor='w')
        font_size_button = tk.Button(
            scrollable_frame,
            text='Set Font Size',
            command=self.change_font_size,
        )
        font_size_button.pack(pady=10, padx=10, anchor='w')
        proxy_button = tk.Button(
            scrollable_frame, text='Set Proxy', command=self.change_proxy
        )
        proxy_button.pack(pady=10, padx=10, anchor='w')
        history_button = tk.Button(
            scrollable_frame,
            text='Set Memory Len',
            command=self.change_history,
        )
        history_button.pack(pady=10, padx=10, anchor='w')

        # Stream 下拉菜单
        stream_label = tk.Label(
            scrollable_frame,
            text='Select Stream Type:',
            font=self.custom_font,
            fg='white',
            bg='black',
        )
        stream_label.pack(pady=10, padx=10, anchor='w')
        stream_combobox = ttk.Combobox(
            scrollable_frame,
            textvariable=self.selected_stream,
            values=self.stream_options,
            state='readonly',
        )
        stream_combobox.pack(pady=10, padx=10, anchor='w')
        stream_combobox.bind(
            '<<ComboboxSelected>>', self.change_stream
        )  # 绑定选择事件

        # Add Always on Top checkbox
        always_on_top_checkbox = tk.Checkbutton(
            scrollable_frame,
            text='Always on Top',
            variable=self.always_on_top,
            onvalue=True,
            offvalue=False,
            command=self.toggle_always_on_top,
        )
        always_on_top_checkbox.pack(pady=10, padx=10, anchor='w')

    def set_window_icon(self, icon_path):
        try:
            img = Image.open(icon_path)
            photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(False, photo)
        except IOError:
            self.show_error_message('crypto_monitor', 'cannot find the icon!')

    def run_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.start_streams())
        self.loop.run_forever()  # 持续运行事件循环

    def run(self):
        self.root.mainloop()
        if self.asyncio_thread:
            self.asyncio_thread.join()

    def on_close(self):
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
        self.root.quit()
        self.root.destroy()
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
