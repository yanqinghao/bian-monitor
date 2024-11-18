import pandas as pd
import requests


class MarketScanner:
    def __init__(self):
        self.base_url = 'https://api.binance.com/api/v3'

    def get_top_symbols(self, top_n=10) -> dict:
        """获取前top_n的交易对（按成交量、涨幅、跌幅）"""
        try:
            print('正在获取24小时交易数据...')
            response = requests.get(f'{self.base_url}/ticker/24hr')
            response.raise_for_status()
            data = response.json()

            # 转换为DataFrame
            df = pd.DataFrame(data)

            # 转换数值类型
            numeric_cols = ['volume', 'quoteVolume', 'priceChangePercent']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 只保留USDT交易对
            usdt_pairs = df[df['symbol'].str.endswith('USDT')].copy()

            # 按不同指标排序并获取前top_n个交易对
            volume_top = usdt_pairs.nlargest(top_n, 'quoteVolume')[
                'symbol'
            ].tolist()
            gainers_top = usdt_pairs.nlargest(top_n, 'priceChangePercent')[
                'symbol'
            ].tolist()
            losers_top = usdt_pairs.nsmallest(top_n, 'priceChangePercent')[
                'symbol'
            ].tolist()

            return {
                'volume': volume_top,
                'gainers': gainers_top,
                'losers': losers_top,
            }

        except Exception as e:
            print(f'获取交易对数据失败: {e}')
            return {}
