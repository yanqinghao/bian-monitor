import pandas as pd
import requests


class MarketScanner:
    def __init__(self):
        self.base_url = 'https://api.binance.com/api/v3'
        # 定义稳定币列表
        self.stablecoins = [
            'USDT',
            'USDC',
            'BUSD',
            'DAI',
            'TUSD',
            'USDP',
            'FDUSD',
            'USDD',
            'USDJ',
            'UST',
            'USDK',
            'USTC',
        ]
        # 编译排除模式
        self.exclude_patterns = [
            f'{coin}{base}'
            for coin in self.stablecoins
            for base in self.stablecoins
        ]

    def get_top_symbols(self, top_n=10) -> dict:
        """获取前top_n的交易对（按成交量、涨幅、跌幅），排除稳定币对"""
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

            # 只保留USDT交易对且排除稳定币
            usdt_pairs = df[
                (df['symbol'].str.endswith('USDT'))
                & (
                    ~df['symbol'].str.contains(
                        '|'.join(self.exclude_patterns), case=True
                    )
                )
                & (~df['symbol'].str.contains('DOWN|UP|BULL|BEAR'))  # 排除杠杆代币
            ].copy()

            # 进一步过滤稳定币
            def is_not_stablecoin(symbol):
                base = 'USDT'  # 基准货币
                coin = symbol[: -len(base)]  # 获取交易对的基础货币部分
                return coin not in self.stablecoins

            usdt_pairs = usdt_pairs[
                usdt_pairs['symbol'].apply(is_not_stablecoin)
            ]

            # 价格过滤（可选，根据需要启用）
            # usdt_pairs = usdt_pairs[
            #     (pd.to_numeric(usdt_pairs['lastPrice'], errors='coerce') > 0.00001)
            # ]

            # 按不同指标排序并获取前top_n个交易对
            volume_top = (
                usdt_pairs.nlargest(top_n, 'quoteVolume')['symbol']
                .str.lower()
                .tolist()
            )
            gainers_top = (
                usdt_pairs.nlargest(top_n, 'priceChangePercent')['symbol']
                .str.lower()
                .tolist()
            )
            losers_top = (
                usdt_pairs.nsmallest(top_n, 'priceChangePercent')['symbol']
                .str.lower()
                .tolist()
            )

            print(f"\n成交量Top{top_n}: {', '.join(volume_top)}")
            print(f"涨幅Top{top_n}: {', '.join(gainers_top)}")
            print(f"跌幅Top{top_n}: {', '.join(losers_top)}")

            return {
                'volume': volume_top,
                'gainers': gainers_top,
                'losers': losers_top,
            }

        except Exception as e:
            print(f'获取交易对数据失败: {e}')
            return {}

    def _is_valid_symbol(self, symbol: str) -> bool:
        """检查交易对是否有效"""
        # 排除稳定币对
        for pattern in self.exclude_patterns:
            if pattern in symbol.upper():
                return False

        # 排除杠杆代币
        if any(x in symbol.upper() for x in ['DOWN', 'UP', 'BULL', 'BEAR']):
            return False

        return True
