import requests
from datetime import datetime, timedelta
import pandas as pd


class DataFetcher:
    @staticmethod
    def get_kline_data(symbol, interval, days, limit=1000):
        """获取K线数据"""
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
            'limit': limit,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return DataFetcher.process_kline_data(response.json())
        except Exception as e:
            raise Exception(f'获取{interval}数据失败: {str(e)}')

    @staticmethod
    def process_kline_data(data):
        """处理K线数据"""
        df = pd.DataFrame(
            data,
            columns=[
                'Open time',
                'Open',
                'High',
                'Low',
                'Close',
                'Volume',
                'Close time',
                'Quote volume',
                'Trades',
                'Buy base',
                'Buy quote',
                'Ignore',
            ],
        )

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
        df.set_index('Open time', inplace=True)

        return df
