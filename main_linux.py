import curses
import threading
from crypto_alert_terminal import CryptoTop


def main(stdscr):
    curses.curs_set(0)  # 隐藏光标
    app = CryptoTop(stdscr)  # 初始化 CryptoTop 应用

    def handle_input():
        while True:
            c = stdscr.getch()  # 获取用户输入
            if c == ord('q'):  # 如果按下 'q' 键
                app.cleanup()  # 清理并退出应用
                break

            # 处理其他按键输入
            elif c == ord('c'):
                app.change_bg_color()
            elif c == ord('f'):
                app.change_font_size()
            elif c == ord('p'):
                app.change_proxy()
            elif c == ord('m'):
                app.change_history()
            elif c == ord('s'):
                app.change_stream()

    # 创建并启动处理输入的线程
    input_thread = threading.Thread(target=handle_input, daemon=True)
    input_thread.start()

    # 运行应用的主循环
    app.run()


if __name__ == '__main__':
    curses.wrapper(main)
