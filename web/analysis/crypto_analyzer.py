from analysis.levels_finder import LevelsFinder

# from analysis.trend_analyzer import TrendAnalyzer
from analysis.indicators import TechnicalIndicators
from analysis.data_fetcher import DataFetcher
from analysis.report_generator import ReportGenerator
from datetime import datetime


class CryptoAnalyzer:
    def __init__(self, symbol, proxies=None):
        self.symbol = symbol
        self.timeframes = {
            '15m': {'days': 7, 'label': '15分钟'},
            '1h': {'days': 15, 'label': '1小时'},
            '4h': {'days': 30, 'label': '4小时'},
            '1d': {'days': 90, 'label': '日线'},
        }
        self.data = {}
        self.proxies = proxies

    def analyze_key_level(self):
        """执行完整分析并生成指定格式的JSON数据"""
        try:
            # 获取数据
            df_1h = DataFetcher.get_kline_data(self.symbol, '1h', 15, proxies=self.proxies)
            current_price = df_1h['Close'].iloc[-1]

            # 计算关键价位
            key_levels = LevelsFinder.find_key_levels(df_1h, current_price)

            # 构建最终JSON
            result = {
                'resistances': [float(x) for x in key_levels['resistances']],
                'supports': [float(x) for x in key_levels['supports']],
            }

            return result

        except Exception as e:
            return {'error': True, 'message': str(e)}

    def analyze(self):
        """执行完整分析并生成指定格式的JSON数据"""
        try:
            # 获取数据
            for interval, info in self.timeframes.items():
                self.data[interval] = DataFetcher.get_kline_data(
                    self.symbol, interval, info['days'], proxies=self.proxies
                )

            # 分析4小时数据作为主要参考
            df_4h = self.data['4h']
            df_1h = self.data['1h']
            current_price = df_1h['Close'].iloc[-1]

            # 计算24小时涨跌幅
            change_24h = (
                (df_1h['Close'].iloc[-1] / df_1h['Close'].iloc[-24]) - 1
            ) * 100

            # 计算各周期指标
            timeframe_analysis = {}
            for interval, df in self.data.items():
                indicators = TechnicalIndicators.calculate_indicators(df)
                analysis = ReportGenerator.analyze_timeframe(df, indicators)
                timeframe_analysis[interval] = {
                    'period': self.timeframes[interval]['label'],
                    **analysis,
                }

            # 计算趋势阶段
            indicators_4h = TechnicalIndicators.calculate_indicators(df_4h)
            trend_stage = ReportGenerator.analyze_trend_stage(
                df_4h, indicators_4h
            )

            # 计算关键价位
            key_levels = LevelsFinder.find_key_levels(df_1h, current_price)

            # 生成交易策略
            trading_strategy = ReportGenerator.generate_signal_based_strategy(
                df_4h,
                key_levels,
                trend_stage,
                indicators_4h,
                trend_stage['volatility'],  # 添加这个参数
            )

            # 构建最终JSON
            result = {
                'basic_info': {
                    'symbol': f'{self.symbol[:-4]}/USDT',
                    'report_time': datetime.now().strftime(
                        '%Y-%m-%d %H:%M:%S'
                    ),
                    'current_price': float(current_price),
                    'change_24h': float(change_24h),
                },
                'trend_analysis': {
                    'current_stage': trend_stage,
                    'timeframe_analysis': timeframe_analysis,
                },
                'key_levels': {
                    'resistances': [
                        float(x) for x in key_levels['resistances']
                    ],
                    'supports': [float(x) for x in key_levels['supports']],
                },
                'trading_strategy': trading_strategy,
                'risk_warnings': [
                    f"当前波动率为 {trend_stage['volatility']:.2f}%，{'建议降低仓位' if trend_stage['volatility'] > 5 else '波动风险适中'}",
                    '大盘走势可能影响个币表现，注意关注大盘动向',
                    '建议严格执行止损策略，控制风险',
                    '不要追高或抄底，耐心等待好的进场点',
                ],
            }

            return result

        except Exception as e:
            return {'error': True, 'message': str(e)}
