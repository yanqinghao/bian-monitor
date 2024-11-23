import requests
from datetime import datetime, timedelta
import pandas as pd


class DataFetcher:
    @staticmethod
    def get_kline_data(symbol, interval, days, limit=1000, proxies=None):
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
            response = requests.get(url, params=params, timeout=30, proxies=proxies)
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

    @staticmethod
    def get_depth_data(symbol, limit=100, proxies=None):
        """
        获取市场深度信息

        参数:
            symbol (str): 交易对符号，例如 'BTCUSDT'
            limit (int): 返回的深度数量，可选值：[5, 10, 20, 50, 100, 500, 1000, 5000]
                        如果 limit > 5000, 最多返回5000条数据

        返回:
            tuple: (bids_df, asks_df) 买单和卖单的DataFrame
        """
        url = 'https://api.binance.com/api/v3/depth'

        params = {'symbol': symbol, 'limit': limit}

        try:
            response = requests.get(url, params=params, timeout=30, proxies=proxies)
            response.raise_for_status()
            return DataFetcher.process_depth_data(response.json())
        except Exception as e:
            raise Exception(f'获取深度数据失败: {str(e)}')

    @staticmethod
    def process_depth_data(data):
        """
        处理深度数据

        参数:
            data (dict): API返回的原始深度数据

        返回:
            tuple: (bids_df, asks_df) 买单和卖单的DataFrame
        """
        # 创建买单DataFrame
        bids_df = pd.DataFrame(data['bids'], columns=['price', 'quantity'])
        # bids_df = bids_df.drop('ignore', axis=1)

        # 创建卖单DataFrame
        asks_df = pd.DataFrame(data['asks'], columns=['price', 'quantity'])
        # asks_df = asks_df.drop('ignore', axis=1)

        # 转换数据类型
        for df in [bids_df, asks_df]:
            df['price'] = pd.to_numeric(df['price'])
            df['quantity'] = pd.to_numeric(df['quantity'])

        return bids_df, asks_df
