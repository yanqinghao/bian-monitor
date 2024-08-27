import aiohttp
import asyncio
import json
from datetime import datetime
import winsound
import tkinter as tk
from tkinter import font as tkFont
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk

eth_threshhold = 2740
btc_threshhold = 63900

def format_timestamp(timestamp):
    timestamp = int(timestamp) / 1000
    dt_object = datetime.fromtimestamp(timestamp)
    formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # 保留小数点后三位
    return formatted_time

class CryptoAlertWindow:
    def __init__(self, root, loop, tasks):
        self.root = root
        self.loop = loop
        self.tasks = tasks
        self.root.title("Crypto Alert")
        self.root.geometry("400x80")  # 调整为长条状的窗口
        self.root.attributes("-topmost", True)
        self.root.configure(bg='black')

        # 设置自定义角标图标
        self.set_window_icon("BTC.png")

        # 使用更小的字体
        self.custom_font = tkFont.Font(family="Arial", size=8, weight="bold")

        # 添加关闭窗口时退出程序的功能
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 创建框架，每个框架占据一行
        self.frame_btc = tk.Frame(self.root, bg='black')
        self.frame_eth = tk.Frame(self.root, bg='black')

        self.frame_btc.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=2)
        self.frame_eth.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=2)

        # BTC 显示区域
        self.label_btc_title = tk.Label(self.frame_btc, text="BTC", font=self.custom_font, fg="white", bg="black")
        self.label_btc_title.pack(side=tk.LEFT)

        self.label_btc_time = tk.Label(self.frame_btc, text="Time: ", font=self.custom_font, fg="white", bg="black")
        self.label_btc_time.pack(side=tk.LEFT, padx=5)

        self.label_btc_price = tk.Label(self.frame_btc, text="Price: ", font=self.custom_font, fg="white", bg="black")
        self.label_btc_price.pack(side=tk.LEFT, padx=5)

        # ETH 显示区域
        self.label_eth_title = tk.Label(self.frame_eth, text="ETH", font=self.custom_font, fg="white", bg="black")
        self.label_eth_title.pack(side=tk.LEFT)

        self.label_eth_time = tk.Label(self.frame_eth, text="Time: ", font=self.custom_font, fg="white", bg="black")
        self.label_eth_time.pack(side=tk.LEFT, padx=5)

        self.label_eth_price = tk.Label(self.frame_eth, text="Price: ", font=self.custom_font, fg="white", bg="black")
        self.label_eth_price.pack(side=tk.LEFT, padx=5)

    def set_window_icon(self, icon_path):
        # 设置自定义窗口图标
        img = Image.open(icon_path)
        img = ImageTk.PhotoImage(img)
        self.root.iconphoto(False, img)

    def update_data(self, name, time, price):
        if name == "BTCUSDT":
            self.label_btc_time.config(text=f"Time: {time}")
            self.label_btc_price.config(text=f"Price: {price}")
        elif name == "ETHUSDT":
            self.label_eth_time.config(text=f"Time: {time}")
            self.label_eth_price.config(text=f"Price: {price}")
        self.root.update_idletasks()

    def on_close(self):
        # 取消所有未完成的任务
        for task in self.tasks:
            task.cancel()

        self.loop.call_soon_threadsafe(self.loop.stop)  # 停止 asyncio 事件循环
        self.root.quit()  # 关闭 tkinter 主循环
        self.root.destroy()  # 销毁窗口，确保退出

    def run(self):
        self.root.mainloop()

async def listen_to_stream(stream_url, proxy_url, alert_window):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(stream_url, proxy=proxy_url) as websocket:
                async for msg in websocket:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        event_time = format_timestamp(data.get('T'))
                        name = data.get('s')
                        price = data.get('p')

                        alert_window.update_data(name, event_time, price)

                        if name == "ETHUSDT" and float(price) > eth_threshhold:
                            winsound.Beep(1000, 500)
                        if name == "BTCUSDT" and float(price) > btc_threshhold:
                            winsound.Beep(1000, 500)
    except asyncio.CancelledError:
        # 正确关闭 WebSocket 连接
        await websocket.close()
        print(f"{stream_url} closed")


async def main(alert_window):
    streams = ['ethusdt@aggTrade', 'btcusdt@aggTrade']
    tasks = []

    proxy_url = 'http://localhost:1081'

    for stream_name in streams:
        stream_url = f"wss://fstream.binance.com/ws/{stream_name}"
        task = asyncio.create_task(listen_to_stream(stream_url, proxy_url, alert_window))
        tasks.append(task)

    # 将任务列表传递给窗口类，以便在关闭时取消
    alert_window.tasks = tasks

    await asyncio.gather(*tasks)

def run_asyncio_loop(loop, alert_window):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main(alert_window))

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    root = tk.Tk()
    alert_window = CryptoAlertWindow(root, loop, tasks=[])

    executor = ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, run_asyncio_loop, loop, alert_window)

    try:
        alert_window.run()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())  # 确保所有异步生成器都已关闭
        loop.close()
