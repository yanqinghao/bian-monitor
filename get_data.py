import requests
import csv
from datetime import datetime, timedelta
import os


def get_kline_data_to_csv(symbol, interval, days, proxy=None, save_dir=None):
    url = 'https://api.binance.com/api/v3/klines'
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int(
        (datetime.now() - timedelta(days=days)).timestamp() * 1000
    )

    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000,
    }

    proxies = {'http': proxy, 'https': proxy} if proxy else None

    try:
        response = requests.get(
            url, params=params, proxies=proxies, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            filename = f"kline_data_{symbol}_{interval}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            if save_dir:
                filename = os.path.join(save_dir, filename)

            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        'Open time',
                        'Open',
                        'High',
                        'Low',
                        'Close',
                        'Volume',
                        'Close time',
                        'Quote asset volume',
                        'Number of trades',
                        'Taker buy base asset volume',
                        'Taker buy quote asset volume',
                    ]
                )
                for kline in data:
                    writer.writerow(kline[:-1])

            print(f'Data saved to {filename}')
        else:
            print(f'Error: {response.status_code}')
            print(response.text)
    except requests.exceptions.RequestException as e:
        print(f'An error occurred: {e}')


def get_user_input(prompt, default=None):
    user_input = (
        input(f'{prompt} [{default}]: ').strip()
        if default
        else input(f'{prompt}: ').strip()
    )
    return user_input if user_input else default


def get_desktop_path():
    return os.path.join(os.path.expanduser('~'), 'Desktop')


def main():
    print('Welcome to the Binance Kline Data Retriever!')

    symbol = get_user_input(
        'Enter the trading pair (e.g., BTCUSDT)', 'BTCUSDT'
    ).upper()
    proxy = get_user_input(
        'Enter proxy address (or press Enter for no proxy)',
        'http://10.33.58.241:1081',
    )

    default_save_dir = get_desktop_path()
    save_dir = get_user_input(
        'Enter save directory (or press Enter for desktop)', default_save_dir
    )

    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
            print(f'Created directory: {save_dir}')
        except OSError as e:
            print(f'Error creating directory {save_dir}: {e}')
            print('Defaulting to desktop.')
            save_dir = default_save_dir

    timeframes = [
        ('1d', 30, '1 day interval for 30 days'),
        ('4h', 7, '4 hour interval for 7 days'),
        ('1h', 3, '1 hour interval for 3 days'),
        ('15m', 1, '15 minute interval for 1 day'),
    ]

    print('\nAvailable timeframes:')
    for i, (interval, days, description) in enumerate(timeframes, 1):
        print(f'{i}. {description}')

    selected = get_user_input(
        "Enter the numbers of timeframes you want to retrieve (comma-separated, or 'all')",
        'all',
    )

    if selected.lower() == 'all':
        selected_timeframes = timeframes
    else:
        indices = [
            int(i.strip()) - 1
            for i in selected.split(',')
            if i.strip().isdigit()
        ]
        selected_timeframes = [
            timeframes[i] for i in indices if 0 <= i < len(timeframes)
        ]

    print(f'\nRetrieving data for {symbol}...')
    for interval, days, description in selected_timeframes:
        print(f'\nGetting {description}...')
        get_kline_data_to_csv(symbol, interval, days, proxy, save_dir)

    print('\nData retrieval complete!')
    input('Press Enter to exit...')


if __name__ == '__main__':
    main()
