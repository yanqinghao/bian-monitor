import asyncio
import tkinter as tk
from crypto_alert_window import CryptoAlertWindow


def main():
    loop = asyncio.new_event_loop()  # 创建一个新的事件循环
    asyncio.set_event_loop(loop)  # 将此事件循环设置为当前线程的默认事件循环
    root = tk.Tk()
    alert_window = CryptoAlertWindow(root, loop)

    try:
        alert_window.run()  # 运行 tkinter 主循环
    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        # 在主循环结束后，确保事件循环正确关闭
        loop.call_soon_threadsafe(loop.stop)
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == '__main__':
    main()
