from services.monitor import MarketMonitor
import time


def main():
    try:
        monitor = MarketMonitor()
        monitor.start_monitoring()

        print('\n按Ctrl+C停止监控')

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        monitor.stop()


if __name__ == '__main__':
    main()
