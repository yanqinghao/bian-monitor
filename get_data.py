import requests
import csv
from datetime import datetime, timedelta


def get_kline_data_to_csv(symbol, interval, days, proxy=None):
    # API endpoint
    url = 'https://api.binance.com/api/v3/klines'  # Replace with the actual API base URL

    # Calculate start time
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int(
        (datetime.now() - timedelta(days=days)).timestamp() * 1000
    )

    # Parameters
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000,  # Maximum number of klines
    }

    # Proxy settings
    proxies = None
    if proxy:
        proxies = {'http': proxy, 'https': proxy}

    try:
        # Send GET request
        response = requests.get(
            url, params=params, proxies=proxies, timeout=30
        )

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()

            # Prepare CSV file
            filename = f"kline_data_{symbol}_{interval}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)

                # Write header
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

                # Write data
                for kline in data:
                    writer.writerow(
                        kline[:-1]
                    )  # Exclude the last unused field

            print(f'Data saved to {filename}')
        else:
            print(f'Error: {response.status_code}')
            print(response.text)
    except requests.exceptions.RequestException as e:
        print(f'An error occurred: {e}')


# Usage
symbol = 'BTCUSDT'  # Replace with your desired trading pair
proxy = 'http://10.33.58.241:1081'  # Replace with your proxy address or set to None if not using a proxy

# Get data for different timeframes
get_kline_data_to_csv(symbol, '1d', 30, proxy)  # 1 day interval for 30 days
get_kline_data_to_csv(symbol, '4h', 7, proxy)  # 4 hour interval for 7 days
get_kline_data_to_csv(symbol, '1h', 3, proxy)  # 1 hour interval for 3 days
get_kline_data_to_csv(symbol, '15m', 1, proxy)  # 15 minute interval for 1 day
