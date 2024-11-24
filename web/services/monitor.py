import numpy as np
import pandas as pd
import threading
import time
import os
import talib
import queue
from itertools import chain
from datetime import datetime, timedelta
from typing import Dict, List
from collections import deque
from services.scan import MarketScanner
from analysis.data_fetcher import DataFetcher
from analysis.crypto_analyzer import CryptoAnalyzer
from analysis.technical_analyzer import TechnicalAnalyzer
from services.notifier import TelegramNotifier
from analysis.pattern_detection import EnhancedPatternDetection
from analysis.pattern_detection import TrendType
from analysis.market_analyzer import EnhancedMarketAnalyzer, MarketCycle

# from dotenv import load_dotenv

# load_dotenv()


class MarketMonitor:
    def __init__(self, symbols: List[str] = [], use_proxy: bool = False):
        # Base configuration
        self.base_url = 'https://api.binance.com/api/v3'
        self.proxies = (
            {'http': 'http://127.0.0.1:1088', 'https': 'http://127.0.0.1:1088'}
            if use_proxy
            else None
        )

        # 添加主要币种列表
        self.major_coins = [
            'btcusdt',
            'ethusdt',
            'solusdt',
            'dogeusdt',
            'bnbusdt',
        ]
        self.user_define_symbols = [s.lower() for s in symbols]
        self.symbols = list(set(self.major_coins + self.user_define_symbols))

        # Data buffers
        self.kline_buffers = {
            symbol: deque(maxlen=100) for symbol in self.symbols
        }
        self.volume_buffers = {
            symbol: deque(maxlen=20) for symbol in self.symbols
        }
        self.key_levels = {}
        self.latest_data = {}
        self.last_alert_time = {}
        self.last_major_analysis_time = {
            coin: datetime.now() - timedelta(hours=1)
            for coin in self.major_coins
        }

        # Analysis components
        self.technical_analyzer = TechnicalAnalyzer()
        self.pattern_detector = EnhancedPatternDetection()
        self.scanner = MarketScanner()
        self.enhanced_analyzer = EnhancedMarketAnalyzer()

        # Thread management
        self.message_queue = queue.Queue()
        self.running = threading.Event()
        self.data_lock = threading.Lock()

        # Initialize Telegram notifier
        self._setup_telegram()

    def _setup_telegram(self):
        """Setup Telegram notification service"""
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

        self.telegram = None
        if telegram_token and telegram_chat_id:
            try:
                self.telegram = TelegramNotifier(
                    telegram_token, telegram_chat_id
                )
            except Exception as e:
                print(f'初始化Telegram通知服务失败: {e}')

    def update_monitoring_list(self):
        """Update monitored symbols list"""
        try:
            print('正在更新监控列表...')
            top_symbols = self.scanner.get_top_symbols(
                top_n=2, proxies=self.proxies
            )

            all_symbols = set()
            for category in ['volume', 'gainers', 'losers']:
                if category in top_symbols:
                    all_symbols.update(top_symbols[category])

            new_symbols = [s.lower() for s in all_symbols]

            added = set(new_symbols) - set(self.symbols)
            removed = set(self.symbols) - set(new_symbols)

            if added:
                print(f"新增监控: {', '.join(added)}")
            if removed:
                print(f"移除监控: {', '.join(removed)}")

            with self.data_lock:
                self.symbols = list(
                    set(
                        self.major_coins
                        + self.user_define_symbols
                        + new_symbols
                    )
                )

                # Update data structures
                for symbol in added:
                    self.kline_buffers[symbol] = deque(maxlen=100)
                    self.volume_buffers[symbol] = deque(maxlen=20)

                for symbol in removed:
                    for data_dict in [
                        self.kline_buffers,
                        self.volume_buffers,
                        self.key_levels,
                        self.latest_data,
                        self.last_alert_time,
                    ]:
                        data_dict.pop(symbol, None)

        except Exception as e:
            print(f'更新监控列表失败: {e}')

    def _initialize_data(self):
        """初始化数据"""
        self.update_monitoring_list()
        print('开始初始化关键价位数据')
        symbols_to_remove = []
        for symbol in self.symbols:
            try:
                with self.data_lock:
                    self.key_levels[symbol] = CryptoAnalyzer(
                        symbol.upper(), proxies=self.proxies
                    ).analyze_key_level()
                    if 0 in list(
                        chain.from_iterable(self.key_levels[symbol].values())
                    ):
                        self.kline_buffers.pop(symbol, None)
                        self.volume_buffers.pop(symbol, None)
                        self.key_levels.pop(symbol, None)
                        self.latest_data.pop(symbol, None)
                        self.last_alert_time.pop(symbol, None)
                        symbols_to_remove.append(symbol)

                    print(f'初始化{symbol}阻力位、支撑位为:{self.key_levels[symbol]}')
            except Exception as e:
                print(f'初始化{symbol}数据失败: {e}')
                self.kline_buffers.pop(symbol, None)
                self.volume_buffers.pop(symbol, None)
                self.key_levels.pop(symbol, None)
                self.latest_data.pop(symbol, None)
                self.last_alert_time.pop(symbol, None)
                symbols_to_remove.append(symbol)

            # finally:
            #     import time

            # time.sleep(1)

        self.symbols = [x for x in self.symbols if x not in symbols_to_remove]

    def _analyze_patterns(self, df: pd.DataFrame, support_resistance) -> Dict:
        """改进的K线形态分析"""
        try:
            # 获取所有K线形态
            candlestick_patterns = (
                self.pattern_detector.detect_candlestick_patterns(df)
            )

            # 获取经典价格形态
            price_patterns = self.pattern_detector.detect_price_patterns(df)

            # 获取趋势线
            trend_lines = self.pattern_detector.detect_trend_lines(df)

            # 获取趋势强度
            trend_strength = self.pattern_detector.get_trend_strength(df)

            # 找出最显著的形态
            significant_patterns = self._find_significant_patterns(
                candlestick_patterns, df
            )

            # 整合所有分析结果
            return {
                'significant_patterns': significant_patterns,  # 最重要的形态
                'candlestick_patterns': candlestick_patterns,  # 保留完整形态分析
                'price_patterns': price_patterns,
                'support_resistance': support_resistance,
                'trend_lines': trend_lines,
                'trend_strength': trend_strength,
            }
        except Exception as e:
            print(f'形态分析失败: {e}')
            return {}

    def _find_significant_patterns(
        self, patterns: Dict, df: pd.DataFrame
    ) -> List[Dict]:
        """
        找出最显著和最可靠的形态

        返回格式:
        [{
            'name': str,
            'type': str (bullish/bearish/neutral),
            'reliability': int (1-5),
            'strength': float (0-1),
            'position': str (formation position),
            'confirms_trend': bool
        }]
        """
        significant = []
        latest_close = df['Close'].iloc[-1]

        # 计算最近的趋势
        sma20 = talib.SMA(df['Close'].values, timeperiod=20)
        trend = 'up' if sma20[-1] > sma20[-2] else 'down'

        for pattern_name, pattern_data in patterns.items():
            signal = pattern_data['signal']
            category = pattern_data['category']

            # 检查最近的信号
            recent_signals = signal.iloc[-3:]  # 检查最近3根K线
            if not any(recent_signals != 0):
                continue

            # 计算形态强度
            pattern_strength = abs(recent_signals.iloc[-1]) / 100

            # 检查形态是否确认趋势
            confirms_trend = (
                trend == 'up' and category.trend_type == TrendType.BULLISH
            ) or (trend == 'down' and category.trend_type == TrendType.BEARISH)

            # 计算形态位置重要性
            position_importance = self._evaluate_pattern_position(
                df, latest_close, pattern_name
            )

            # 只保留重要的形态
            if (
                category.reliability >= 4
                or confirms_trend  # 高可靠度形态
                or position_importance >= 0.8  # 确认趋势的形态
            ):  # 重要位置的形态

                significant.append(
                    {
                        'name': category.name,
                        'type': category.trend_type.value,
                        'reliability': category.reliability,
                        'strength': pattern_strength,
                        'position_importance': position_importance,
                        'confirms_trend': confirms_trend,
                    }
                )

        # 按重要性排序
        significant.sort(
            key=lambda x: (
                x['reliability'],
                x['strength'],
                x['position_importance'],
            ),
            reverse=True,
        )

        # 最多返回3个最重要的形态
        return significant[:3]

    def _evaluate_pattern_position(
        self, df: pd.DataFrame, current_price: float, pattern_name: str
    ) -> float:
        """评估形态出现位置的重要性"""
        importance = 0.5  # 基础重要性

        # 计算关键价位
        high = df['High'].max()
        low = df['Low'].min()
        range_size = high - low

        # 检查是否在支撑/阻力位附近
        nearest_support = None
        nearest_resistance = None

        # 计算支撑位
        for i in range(len(df) - 20, len(df)):
            if df['Low'].iloc[i] == df['Low'].iloc[i:].min():
                nearest_support = df['Low'].iloc[i]
                break

        # 计算阻力位
        for i in range(len(df) - 20, len(df)):
            if df['High'].iloc[i] == df['High'].iloc[i:].max():
                nearest_resistance = df['High'].iloc[i]
                break

        # 根据位置调整重要性
        if (
            nearest_support
            and abs(current_price - nearest_support) / range_size < 0.02
        ):
            importance += 0.3  # 靠近支撑位
        if (
            nearest_resistance
            and abs(current_price - nearest_resistance) / range_size < 0.02
        ):
            importance += 0.3  # 靠近阻力位

        # 考虑成交量确认
        volume = df['Volume'].iloc[-1]
        avg_volume = df['Volume'].rolling(window=20).mean().iloc[-1]
        if volume > avg_volume * 1.5:
            importance += 0.2  # 成交量放大

        return min(1.0, importance)

    def _analyze_major_coin(self, symbol: str, market_analysis: Dict) -> str:
        """
        分析主要币种的形态和策略，集成市场周期分析

        Args:
            symbol: 交易对
            market_analysis: 市场周期分析结果
        """
        try:
            # 获取不同时间周期的K线数据
            klines_4h = DataFetcher.get_kline_data(
                symbol.upper(), '4h', 30, proxies=self.proxies
            )
            klines_1h = DataFetcher.get_kline_data(
                symbol.upper(), '1h', 15, proxies=self.proxies
            )

            # 进行形态分析
            patterns_4h = self._analyze_patterns(
                klines_4h, self.key_levels[symbol]['4h']
            )
            patterns_1h = self._analyze_patterns(
                klines_1h, self.key_levels[symbol]['1h']
            )

            current_price = float(klines_1h['Close'].iloc[-1])

            # 生成分析报告
            message = (
                f'🔄 {symbol.upper()} 市场分析报告\n\n'
                f'💰 当前价格: {current_price:.2f} USDT\n'
            )

            # 添加市场周期信息
            if market_analysis:
                message += (
                    f'\n🌍 市场状态:\n'
                    f"• 市场周期: {market_analysis['market_cycle'].value}\n"
                    f"• 趋势强度: {market_analysis['trend_strength']:.2f}\n"
                )

                # 添加支撑/阻力位信息
                sr_analysis = market_analysis['support_resistance']
                if sr_analysis['nearest_support']:
                    message += (
                        f"• 关键支撑: {sr_analysis['nearest_support']:.2f}\n"
                    )
                if sr_analysis['nearest_resistance']:
                    message += (
                        f"• 关键阻力: {sr_analysis['nearest_resistance']:.2f}\n"
                    )

                # 添加突破/跌破信息
                if 'breakdown_breakout' in market_analysis:
                    bb_info = market_analysis['breakdown_breakout']
                    if bb_info['type'] != 'none':
                        message += (
                            f"• {'突破' if bb_info['type'] == 'breakout' else '跌破'}"
                            f"位置: {bb_info['level']:.2f}\n"
                        )

            # 添加4小时周期分析
            message += '\n📊 4小时周期分析:\n'
            if patterns_4h:
                # 分析趋势强度
                trend_str = '看涨' if patterns_4h['trend_strength'] > 0 else '看跌'
                strength = abs(patterns_4h['trend_strength'])
                message += f'• 趋势: {trend_str} (强度: {strength:.2f})\n'

                # 添加显著的K线形态
                if 'significant_patterns' in patterns_4h:
                    significant_patterns = []
                    for pattern in patterns_4h['significant_patterns']:
                        significant_patterns.append(
                            f"{pattern['name']}({'确认趋势' if pattern['confirms_trend'] else pattern['type']})"
                        )

                    if significant_patterns:
                        message += (
                            f"• 主要形态: {', '.join(significant_patterns)}\n"
                        )

                # 添加支撑压力位
                sr_levels = patterns_4h['support_resistance']
                if sr_levels:
                    supports = sr_levels.get('supports', [])
                    resistances = sr_levels.get('resistances', [])
                    if supports:
                        message += f'• 近期支撑位: {supports[0]:.2f}\n'
                    if resistances:
                        message += f'• 近期压力位: {resistances[0]:.2f}\n'

            # 添加1小时周期分析
            message += '\n⏰ 1小时周期分析:\n'
            if patterns_1h:
                trend_str = '看涨' if patterns_1h['trend_strength'] > 0 else '看跌'
                strength = abs(patterns_1h['trend_strength'])
                message += f'• 趋势: {trend_str} (强度: {strength:.2f})\n'

                # 分析短期形态
                if 'significant_patterns' in patterns_1h:
                    short_term_patterns = []
                    for pattern in patterns_1h['significant_patterns']:
                        if pattern['reliability'] >= 3:
                            short_term_patterns.append(
                                f"{pattern['name']}({pattern['type']})"
                            )

                    if short_term_patterns:
                        message += (
                            f"• 当前形态: {', '.join(short_term_patterns)}\n"
                        )

            # 在添加交易建议之前,计算入场点位
            entry_points = self._calculate_entry_points(
                current_price=current_price,
                market_analysis=market_analysis,
                patterns_4h=patterns_4h,
                patterns_1h=patterns_1h,
                sr_levels=patterns_1h['support_resistance'],  # 使用1小时周期的支撑阻力位
            )

            # 添加交易建议
            message += '\n💡 交易建议:\n'

            # 根据市场周期和技术形态综合分析
            if market_analysis:
                cycle = market_analysis['market_cycle']
                trend_strength = market_analysis['trend_strength']
                ma_trend = market_analysis['ma_trend']

                # 生成周期建议
                cycle_advice = self._generate_cycle_advice(
                    cycle,
                    trend_strength,
                    patterns_4h['trend_strength'],
                    patterns_1h['trend_strength'],
                )
                message += cycle_advice

                # 添加入场点位建议
                if entry_points:
                    message += '\n📍 入场建议:\n'
                    if entry_points.get('entry', []):
                        message += f"• 建议入场区间: {' - '.join([f'{p:.2f}' for p in entry_points['entry']])}\n"
                    if entry_points.get('stop_loss'):
                        message += f"• 建议止损: {entry_points['stop_loss']:.2f}\n"
                    if entry_points.get('take_profit', []):
                        message += f"• 目标位: {' -> '.join([f'{p:.2f}' for p in entry_points['take_profit']])}\n"

                # 添加风险提示
                risk_warning = self._generate_risk_warning(
                    market_analysis, current_price
                )
                if risk_warning:
                    message += f'\n⚠️ 风险提示:\n{risk_warning}'
            else:
                # 如果没有市场周期分析,使用简单的趋势分析
                if (
                    patterns_4h['trend_strength'] > 0.5
                    and patterns_1h['trend_strength'] > 0.3
                ):
                    message += '• 建议做多,注意设置止损\n'
                    if entry_points:
                        message += self._format_entry_advice(
                            entry_points, 'long'
                        )
                elif (
                    patterns_4h['trend_strength'] < -0.5
                    and patterns_1h['trend_strength'] < -0.3
                ):
                    message += '• 建议做空,注意设置止损\n'
                    if entry_points:
                        message += self._format_entry_advice(
                            entry_points, 'short'
                        )
                else:
                    message += '• 建议观望,等待更清晰的信号\n'

            return message

        except Exception as e:
            print(f'分析主要币种失败 {symbol}: {e}')
            import traceback

            traceback.print_exc()
            return ''

    def _calculate_entry_points(
        self,
        current_price: float,
        market_analysis: Dict,
        patterns_4h: Dict,
        patterns_1h: Dict,
        sr_levels: Dict,
    ) -> Dict:
        """计算建议的入场点位、止损和目标位"""
        entry_points = {'entry': [], 'stop_loss': None, 'take_profit': []}

        try:
            # 获取最近的支撑位和阻力位
            supports = sorted(
                [
                    s
                    for s in sr_levels.get('supports', [])
                    if s < current_price
                ],
                reverse=True,
            )
            resistances = sorted(
                [
                    r
                    for r in sr_levels.get('resistances', [])
                    if r > current_price
                ]
            )

            # 根据市场周期和趋势确定方向
            if market_analysis:
                cycle = market_analysis['market_cycle']
                trend_strength = market_analysis['trend_strength']

                # 多头入场点位计算
                if (
                    cycle in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]
                    and trend_strength > 0.3
                ) or (
                    patterns_4h['trend_strength'] > 0.5
                    and patterns_1h['trend_strength'] > 0.3
                ):
                    # 计算入场区间
                    if supports:
                        # 支撑位上方1-2%
                        entry_low = supports[0] * 1.01
                        entry_high = supports[0] * 1.02
                        entry_points['entry'] = [entry_low, entry_high]
                        # 支撑位下方1-2%设置止损
                        entry_points['stop_loss'] = supports[0] * 0.98

                    # 设置目标位
                    if resistances:
                        # 第一目标位
                        entry_points['take_profit'].append(resistances[0])
                        # 第二目标位(阻力位上方3%)
                        if len(resistances) > 1:
                            entry_points['take_profit'].append(resistances[1])
                        else:
                            entry_points['take_profit'].append(
                                resistances[0] * 1.03
                            )

                # 空头入场点位计算
                elif (
                    cycle in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]
                    and trend_strength < -0.3
                ) or (
                    patterns_4h['trend_strength'] < -0.5
                    and patterns_1h['trend_strength'] < -0.3
                ):
                    if resistances:
                        # 阻力位下方1-2%
                        entry_high = resistances[0] * 0.99
                        entry_low = resistances[0] * 0.98
                        entry_points['entry'] = [entry_low, entry_high]
                        # 阻力位上方2%设置止损
                        entry_points['stop_loss'] = resistances[0] * 1.02

                    # 设置目标位
                    if supports:
                        # 第一目标位
                        entry_points['take_profit'].append(supports[0])
                        # 第二目标位(支撑位下方3%)
                        if len(supports) > 1:
                            entry_points['take_profit'].append(supports[1])
                        else:
                            entry_points['take_profit'].append(
                                supports[0] * 0.97
                            )

                # 根据市场波动调整止损
                if entry_points['stop_loss']:
                    volatility = market_analysis.get('volatility', {}).get(
                        'atr_percent', 2
                    )
                    if volatility > 3:  # 高波动市场
                        entry_points['stop_loss'] = self._adjust_stop_loss(
                            entry_points['stop_loss'],
                            current_price,
                            volatility,
                            cycle,
                        )

        except Exception as e:
            print(f'计算入场点位失败: {e}')

        return entry_points

    def _adjust_stop_loss(
        self,
        stop_loss: float,
        current_price: float,
        volatility: float,
        market_cycle: MarketCycle,
    ) -> float:
        """根据波动率和市场周期调整止损位"""
        # 基础止损率
        base_risk = 0.02  # 2%

        # 根据波动率调整
        if volatility > 5:  # 高波动
            risk = base_risk * 1.5
        elif volatility > 3:  # 中等波动
            risk = base_risk * 1.2
        else:  # 低波动
            risk = base_risk

        # 根据市场周期进一步调整
        if market_cycle in [
            MarketCycle.BULL_BREAKOUT,
            MarketCycle.BEAR_BREAKDOWN,
        ]:
            risk *= 1.2  # 突破/跌破时设置更宽松的止损

        # 计算新的止损位
        if stop_loss > current_price:  # 做空止损
            return stop_loss * (1 + risk)
        else:  # 做多止损
            return stop_loss * (1 - risk)

    def _format_entry_advice(self, entry_points: Dict, direction: str) -> str:
        """格式化入场建议"""
        advice = ''
        if entry_points.get('entry'):
            advice += f"• 建议{direction=='long' and '买入' or '卖出'}区间: "
            advice += (
                f"{' - '.join([f'{p:.2f}' for p in entry_points['entry']])}\n"
            )

        if entry_points.get('stop_loss'):
            advice += f"• 建议止损位: {entry_points['stop_loss']:.2f}\n"

        if entry_points.get('take_profit'):
            targets = entry_points['take_profit']
            advice += f"• 目标位: {' -> '.join([f'{p:.2f}' for p in targets])}\n"

        return advice

    def _generate_risk_warning(
        self, market_analysis: Dict, current_price: float
    ) -> str:
        """生成风险提示信息"""
        warnings = []

        # 检查趋势强度风险
        trend_strength = market_analysis['trend_strength']
        if abs(trend_strength) > 0.8:
            warnings.append(f'• 趋势过热，注意可能的回调风险')

        # 检查价格位置风险
        sr_analysis = market_analysis['support_resistance']
        if sr_analysis['position'] == 'at_resistance':
            warnings.append('• 当前价格接近强阻力位，突破失败可能回落')
        elif sr_analysis['position'] == 'at_support':
            warnings.append('• 当前价格处于支撑位，跌破可能加速下跌')

        # 检查市场周期风险
        cycle = market_analysis['market_cycle']
        if cycle in [MarketCycle.BULL_BREAKOUT, MarketCycle.BEAR_BREAKDOWN]:
            warnings.append('• 突破/跌破初期，注意假突破风险')

        # 检查趋势一致性风险
        ma_trend = market_analysis['ma_trend']
        if ma_trend['alignment'] == 'neutral':
            warnings.append('• 均线系统混乱，建议等待趋势明确')

        return '\n'.join(warnings) if warnings else ''

    def _monitor_abnormal_movements(
        self, symbol: str, indicators: Dict, volume_data: Dict
    ):
        """监控多时间周期的异常波动并发送Telegram通知"""
        try:
            messages = []
            timeframes = {'1h': '1小时', '15m': '15分钟'}

            # 检查各个时间周期的价格波动
            for tf in timeframes:
                if tf in indicators and 'volatility' in indicators[tf]:
                    volatility = indicators[tf].get('volatility', {})
                    atr_percent = volatility.get('atr_percent', 0)

                    # 不同时间周期使用不同的阈值
                    atr_threshold = 5 if tf == '1h' else 3  # 15分钟用较小阈值

                    if atr_percent > atr_threshold:
                        price_alert = (
                            f'⚠️ {timeframes[tf]}价格波动提醒 ⚠️\n\n'
                            f'🎯 交易对: <b>{symbol.upper()}</b>\n'
                            f'📊 ATR波幅: <code>{atr_percent:.2f}%</code>\n'
                            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f'\n📈 波动详情:\n'
                        )

                        # 添加肯特纳通道信息
                        if 'keltner' in volatility:
                            keltner = volatility['keltner']
                            price_alert += (
                                f'• 肯特纳通道:\n'
                                f"  上轨: <code>{keltner.get('upper', 0):.2f}</code>\n"
                                f"  中轨: <code>{keltner.get('middle', 0):.2f}</code>\n"
                                f"  下轨: <code>{keltner.get('lower', 0):.2f}</code>\n"
                            )

                        # 添加价格波动统计
                        if 'price_volatility' in volatility:
                            price_vol = volatility['price_volatility']
                            price_alert += (
                                f"• 价格区间: <code>{price_vol.get('price_range', 0):.2f}</code>\n"
                                f"• 高低比: <code>{price_vol.get('high_low_ratio', 0):.2f}</code>\n"
                            )

                        # 添加趋势信息
                        if 'trend' in indicators[tf]:
                            trend = indicators[tf]['trend']
                            trend_str = (
                                '上涨'
                                if trend.get('direction') == 'up'
                                else '下跌'
                            )
                            trend_strength = trend.get('strength', 0)
                            price_alert += (
                                f'\n📊 趋势分析:\n'
                                f'• 方向: {trend_str}\n'
                                f'• 强度: <code>{trend_strength:.1f}</code>\n'
                            )

                        messages.append(price_alert)
                        print(
                            f'\n⚠️ {symbol} {timeframes[tf]}价格波动异常: {atr_percent:.2f}%'
                        )

            # 检查成交量异常 - 分时间周期
            for tf in timeframes:
                if tf in volume_data:
                    volume_ratio = volume_data[tf].get('ratio', 1)
                    pressure_ratio = volume_data[tf].get('pressure_ratio', 1)

                    # 不同时间周期使用不同的阈值
                    volume_threshold = 10 if tf == '1h' else 5  # 15分钟用较小阈值

                    if volume_ratio > volume_threshold:
                        volume_alert = (
                            f'⚠️ {timeframes[tf]}成交量异常提醒 ⚠️\n\n'
                            f'🎯 交易对: <b>{symbol.upper()}</b>\n'
                            f'📊 成交量比率: <code>{volume_ratio:.2f}倍</code>\n'
                            f'⚖️ 买卖比: <code>{pressure_ratio:.2f}</code>\n'
                            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f'\n📈 成交量分析:\n'
                        )

                        # 添加成交量详情
                        tf_volume_data = volume_data[tf]
                        if (
                            'current_volume' in tf_volume_data
                            and 'avg_volume' in tf_volume_data
                        ):
                            volume_alert += (
                                f"• 当前成交量: <code>{tf_volume_data['current_volume']:.2f}</code>\n"
                                f"• 平均成交量: <code>{tf_volume_data['avg_volume']:.2f}</code>\n"
                            )

                        # 分析买卖压力
                        pressure_status = (
                            '买方强势'
                            if pressure_ratio > 1.5
                            else '卖方强势'
                            if pressure_ratio < 0.7
                            else '买卖平衡'
                        )
                        volume_alert += f'• 市场状态: {pressure_status}\n'

                        # 添加成交量趋势分析
                        if 'volume_trend' in tf_volume_data:
                            v_trend = tf_volume_data['volume_trend']
                            volume_alert += (
                                f'\n📊 成交量趋势:\n'
                                f"• 连续放量: <code>{v_trend.get('consecutive_increase', 0)}</code>次\n"
                                f"• 累计涨幅: <code>{v_trend.get('total_increase', 0):.2f}%</code>\n"
                            )

                        messages.append(volume_alert)
                        print(
                            f'\n⚠️ {symbol} {timeframes[tf]}成交量异常: '
                            f'当前量是均量的 {volume_ratio:.2f} 倍'
                        )

            # 判断多时间周期的综合异常
            if len(messages) >= 2:  # 如果多个时间周期都出现异常
                combined_alert = (
                    f'🚨 多时间周期异常警报 🚨\n\n'
                    f'🎯 交易对: <b>{symbol.upper()}</b>\n'
                    f'⚠️ 警告: 多个时间周期同时出现异常波动，风险较大！\n'
                    f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                messages.insert(0, combined_alert)  # 将综合警报放在最前面

            # 发送Telegram通知
            if messages and self.telegram:
                # 添加风险提示
                # risk_warning = (
                #     "\n⚠️ 风险提示:\n"
                #     "• 异常波动可能带来剧烈价格变动\n"
                #     "• 建议适当调整仓位和止损\n"
                #     "• 请勿盲目追涨杀跌\n"
                #     "• 确保资金安全和风险控制"
                # )
                self.telegram.rev_alert_message(messages)

        except Exception as e:
            print(f'监控异常波动时出错: {e}')

    def _prepare_volume_data(self, symbol: str) -> Dict:
        """
        Improved volume data processing using direct market depth data
        """
        try:
            volume_data = {}

            # Get current market depth data
            bids_df, asks_df = DataFetcher.get_depth_data(
                symbol.upper(), limit=20, proxies=self.proxies
            )

            # Calculate current volumes
            current_bid_volume = bids_df['quantity'].sum()
            current_ask_volume = asks_df['quantity'].sum()
            current_volume = current_bid_volume + current_ask_volume

            # Get historical kline data for volume comparison (last 20 periods)
            historical_klines = DataFetcher.get_kline_data(
                symbol.upper(), '5m', 1, limit=20, proxies=self.proxies
            )

            if not historical_klines.empty:
                # Calculate weighted average volume from historical data
                weights = np.linspace(0.5, 1.0, len(historical_klines))
                historical_volumes = historical_klines['Volume'].values
                avg_volume = np.average(historical_volumes, weights=weights)

                volume_data = {
                    'bid_volume': current_bid_volume,
                    'ask_volume': current_ask_volume,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'ratio': current_volume / avg_volume
                    if avg_volume > 0
                    else 1.0,
                    'pressure_ratio': current_bid_volume / current_ask_volume
                    if current_ask_volume > 0
                    else 1.0,
                }

                # Calculate additional metrics for multiple timeframes
                volume_data.update(
                    {
                        '15m': {
                            'current_volume': current_volume,
                            'avg_volume': avg_volume,
                            'ratio': current_volume / avg_volume
                            if avg_volume > 0
                            else 1.0,
                            'pressure_ratio': current_bid_volume
                            / current_ask_volume
                            if current_ask_volume > 0
                            else 1.0,
                        }
                    }
                )

                # Get 1h historical data for hourly analysis
                hourly_klines = DataFetcher.get_kline_data(
                    symbol.upper(), '1h', 1, limit=20, proxies=self.proxies
                )
                if not hourly_klines.empty:
                    hourly_avg_volume = np.average(
                        hourly_klines['Volume'].values,
                        weights=np.linspace(0.5, 1.0, len(hourly_klines)),
                    )
                    hourly_current = (
                        current_volume * 12
                    )  # Approximate hourly volume

                    volume_data['1h'] = {
                        'current_volume': hourly_current,
                        'avg_volume': hourly_avg_volume,
                        'ratio': hourly_current / hourly_avg_volume
                        if hourly_avg_volume > 0
                        else 1.0,
                        'pressure_ratio': current_bid_volume
                        / current_ask_volume
                        if current_ask_volume > 0
                        else 1.0,
                    }

                # Add volume trend analysis
                volume_trend = {'consecutive_increase': 0, 'total_increase': 0}

                # Calculate consecutive volume increases
                volumes = historical_klines['Volume'].values
                for i in range(len(volumes) - 1, 0, -1):
                    if volumes[i] > volumes[i - 1]:
                        volume_trend['consecutive_increase'] += 1
                        volume_trend['total_increase'] += (
                            (volumes[i] - volumes[i - 1])
                            / volumes[i - 1]
                            * 100
                        )
                    else:
                        break

                volume_data['volume_trend'] = volume_trend

            return volume_data

        except Exception as e:
            print(f'准备成交量数据时出错: {e}')
            return {}

    def _generate_cycle_advice(
        self,
        cycle: MarketCycle,
        trend_strength: float,
        trend_4h: float,
        trend_1h: float,
    ) -> str:
        """生成基于市场周期的交易建议"""
        advice = ''

        # 强势牛市情况
        if cycle == MarketCycle.BULL and trend_strength > 0.7:
            if trend_4h > 0 and trend_1h > 0:
                advice += (
                    '• 强势牛市，可以考虑逢低买入\n'
                    '• 建议采用追踪止损策略\n'
                    f'• 当前趋势强度高({trend_strength:.2f})，注意波动风险\n'
                )
            else:
                advice += '• 短期调整，可以等待回调买入\n' '• 关注支撑位表现\n'

        # 牛市突破情况
        elif cycle == MarketCycle.BULL_BREAKOUT:
            advice += '• 突破形态确认，可以考虑顺势追多\n' '• 设置较近的保护性止损\n' '• 注意成交量配合\n'

        # 熊市情况
        elif cycle == MarketCycle.BEAR and trend_strength < -0.7:
            if trend_4h < 0 and trend_1h < 0:
                advice += (
                    '• 强势熊市，建议观望或轻仓做空\n'
                    '• 注意反弹风险\n'
                    f'• 下跌趋势强劲({trend_strength:.2f})，保持谨慎\n'
                )
            else:
                advice += '• 可能出现短期反弹\n' '• 不建议追空，等待回落后再考虑\n'

        # 熊市崩盘情况
        elif cycle == MarketCycle.BEAR_BREAKDOWN:
            advice += '• 跌破重要支撑，风险较大\n' '• 建议观望或谨慎做空\n' '• 注意市场恐慌情绪\n'

        # 震荡市场
        elif cycle == MarketCycle.CONSOLIDATION:
            advice += '• 市场处于震荡整理阶段\n' '• 建议等待方向明确\n' '• 可以关注区间交易机会\n'

        return advice

    def _output_signals(
        self,
        symbol: str,
        signals: List[Dict],
        current_time: datetime,
        current_price: float,
        volume_data: Dict,
    ):
        """改进的信号输出，包含多时间周期信息"""
        if not signals:
            return

        # 检查冷却时间
        if symbol in self.last_alert_time:
            cooldown = (
                180
                if any(
                    s['type'] in ['strong_buy', 'strong_sell'] for s in signals
                )
                else 300
            )
            if (
                current_time - self.last_alert_time[symbol]
            ).total_seconds() < cooldown:
                return

        print(f'\n{"="*50}')
        print(
            f'交易对: {symbol.upper()} - 时间: {current_time.strftime("%Y-%m-%d %H:%M:%S")}'
        )
        print(f'当前价格: {current_price:.8f}')

        if volume_data:
            volume_color = '🔴' if volume_data.get('ratio', 1) > 2 else '⚪️'
            pressure_color = (
                '🔴'
                if volume_data.get('pressure_ratio', 1) > 1.5
                else (
                    '🔵' if volume_data.get('pressure_ratio', 1) < 0.7 else '⚪️'
                )
            )
            print(f'成交量比率: {volume_color} {volume_data["ratio"]:.2f}')
            print(f'买卖比: {pressure_color} {volume_data["pressure_ratio"]:.2f}')

        for signal in signals:
            signal_type_map = {
                'strong_buy': '🔥🔥🔥 强力买入',
                'buy': '📈 买入',
                'sell': '📉 卖出',
                'strong_sell': '❄️❄️❄️ 强力卖出',
            }

            print(f"\n信号类型: {signal_type_map.get(signal['type'], '🔍 观察')}")
            print(f"信号强度: {signal['score']:.1f}/100")

            # 输出各时间周期的技术得分
            technical_scores = signal.get('technical_score', {})
            if technical_scores:
                print('\n技术得分:')
                if '4h' in technical_scores:
                    print(f"- 4小时: {technical_scores['4h']:.1f}")
                if '1h' in technical_scores:
                    print(f"- 1小时: {technical_scores['1h']:.1f}")
                if '15m' in technical_scores:
                    print(f"- 15分钟: {technical_scores['15m']:.1f}")

            # 输出趋势一致性信息
            if 'trend_alignment' in signal:
                print(f"趋势一致性: {signal['trend_alignment']}")

            print(f"支阻得分: {signal.get('sr_score', 0):.1f}")
            print(f"成交量得分: {signal.get('volume_score', 0):.1f}")

            if 'risk_level' in signal:
                risk_level_map = {
                    'high': '⚠️ 高风险',
                    'medium': '⚡️ 中等风险',
                    'low': '✅ 低风险',
                }
                print(
                    f"风险等级: {risk_level_map.get(signal['risk_level'], '未知风险')}"
                )

            if 'reason' in signal:
                print(f"触发原因: {signal['reason']}")

        self.last_alert_time[symbol] = current_time
        print(f'{"="*50}\n')

    def _periodic_update_levels(self):
        """定期更新关键价位"""
        while self.running.is_set():
            try:
                # 一小时更新一次
                time.sleep(3600)
                self.update_monitoring_list()
                symbols_to_remove = []
                for symbol in self.symbols:
                    with self.data_lock:
                        self.key_levels[symbol] = CryptoAnalyzer(
                            symbol, proxies=self.proxies
                        ).analyze_key_level()
                        print(f'已更新 {symbol} 的关键价位')
                        if 0 in list(
                            chain.from_iterable(
                                self.key_levels[symbol].values()
                            )
                        ):
                            self.kline_buffers.pop(symbol, None)
                            self.volume_buffers.pop(symbol, None)
                            self.key_levels.pop(symbol, None)
                            self.latest_data.pop(symbol, None)
                            self.last_alert_time.pop(symbol, None)
                            symbols_to_remove.append(symbol)

                self.symbols = [
                    x for x in self.symbols if x not in symbols_to_remove
                ]

            except Exception as e:
                print(f'更新关键价位失败: {e}')
                time.sleep(60)  # 出错后等待1分钟再试

    def _analysis_loop(self):
        """改进的分析循环，包含形态分析和主要币种定期报告"""
        while self.running.is_set():
            try:
                current_time = datetime.now()
                batch_signals = []

                # 检查主要币种的每小时分析
                for symbol in self.major_coins:
                    last_analysis = self.last_major_analysis_time[symbol]
                    if (
                        current_time - last_analysis
                    ).total_seconds() >= 3600:  # 一小时
                        # 获取90天日线数据用于市场周期分析
                        daily_data = DataFetcher.get_kline_data(
                            symbol.upper(), '1d', 90, proxies=self.proxies
                        )

                        # 使用新的分析器进行分析
                        market_analysis = (
                            self.enhanced_analyzer.analyze_market_state(
                                daily_data, float(daily_data['Close'].iloc[-1])
                            )
                        )

                        analysis_message = self._analyze_major_coin(
                            symbol, market_analysis
                        )
                        print(analysis_message)
                        if analysis_message and self.telegram:
                            self.telegram.send_message(analysis_message)
                        self.last_major_analysis_time[symbol] = current_time

                # 处理所有币种的5分钟扫描
                for symbol in self.symbols:
                    try:
                        # 获取各时间周期数据
                        klines_4h = DataFetcher.get_kline_data(
                            symbol.upper(), '4h', 15, proxies=self.proxies
                        )
                        klines_1h = DataFetcher.get_kline_data(
                            symbol.upper(), '1h', 15, proxies=self.proxies
                        )
                        klines_15m = DataFetcher.get_kline_data(
                            symbol.upper(), '15m', 15, proxies=self.proxies
                        )
                        daily_data = DataFetcher.get_kline_data(
                            symbol.upper(), '1d', 90, proxies=self.proxies
                        )

                        # 格式化K线数据
                        kline_data_4h = [
                            self._format_kline_data(row)
                            for _, row in klines_4h.iterrows()
                        ]
                        kline_data_1h = [
                            self._format_kline_data(row)
                            for _, row in klines_1h.iterrows()
                        ]
                        kline_data_15m = [
                            self._format_kline_data(row)
                            for _, row in klines_15m.iterrows()
                        ]

                        current_price = float(klines_1h['Close'].iloc[-1])

                        # 准备成交量数据
                        volume_data = self._prepare_volume_data(symbol)

                        if not all(
                            [
                                kline_data_4h,
                                kline_data_1h,
                                kline_data_15m,
                                volume_data,
                            ]
                        ):
                            continue

                        # 市场周期分析
                        market_analysis = (
                            self.enhanced_analyzer.analyze_market_state(
                                daily_data, current_price
                            )
                        )

                        # 计算技术指标
                        indicators = (
                            self.technical_analyzer.calculate_indicators(
                                kline_data_4h,
                                kline_data_1h,
                                kline_data_15m,
                            )
                        )

                        # 形态分析
                        pattern_analysis = self._analyze_patterns(
                            klines_1h, self.key_levels[symbol]['1h']
                        )

                        # 生成交易信号
                        signals = (
                            self.technical_analyzer.generate_trading_signals(
                                indicators=indicators,
                                price=current_price,
                                key_levels=self.key_levels.get(symbol, {})[
                                    '1h'
                                ],
                                volume_data=volume_data,
                                pattern_analysis=pattern_analysis,
                                market_analysis=market_analysis,
                            )
                        )

                        # 处理信号
                        if signals:
                            # 更新信号描述
                            enhanced_signals = [
                                self.technical_analyzer.update_signal_description(
                                    signal
                                )
                                for signal in signals
                            ]

                            # 输出信号
                            self._output_signals(
                                symbol,
                                enhanced_signals,
                                current_time,
                                current_price,
                                volume_data,
                                market_analysis,
                            )

                            # 添加到批量信号
                            batch_signals.extend(
                                [
                                    {
                                        'symbol': symbol,
                                        'price': current_price,
                                        'signal': signal,
                                        'market_analysis': market_analysis,
                                        'volume_data': volume_data,
                                    }
                                    for signal in enhanced_signals
                                ]
                            )

                        # # 监控异常波动
                        # self._monitor_abnormal_movements(
                        #     symbol, indicators, volume_data
                        # )

                    except Exception as e:
                        print(f'处理{symbol}数据时出错: {e}')
                        continue

                # 发送批量信号
                if batch_signals and self.telegram:
                    self._send_enhanced_batch_alerts(batch_signals)

                time.sleep(300)  # 5分钟检查一次

            except Exception as e:
                print(f'分析过程出错: {e}')
                import traceback

                traceback.print_exc()
                time.sleep(0.1)

    def _send_enhanced_batch_alerts(self, batch_signals: List[Dict]):
        """发送增强版批量信号提醒"""
        if not self.telegram:
            return

        for signal_data in batch_signals:
            signal = signal_data['signal']
            market_analysis = signal_data['market_analysis']
            volume_data = signal_data['volume_data']

            # 构建更详细的消息
            technical_scores = signal.get('technical_score', {})
            scores_text = []
            for tf in ['4h', '1h', '15m']:
                if tf in technical_scores:
                    scores_text.append(f'{tf}:{technical_scores[tf]:.1f}')

            # 市场周期信息
            cycle_info = (
                f"\n🌍 市场周期: {market_analysis['market_cycle'].value}\n"
                f"📊 趋势强度: {market_analysis['trend_strength']:.2f}"
                if market_analysis
                else ''
            )

            # 风险评估信息
            risk_info = ''
            if 'risk_assessment' in signal:
                risk = signal['risk_assessment']
                risk_info = (
                    f"\n⚠️ 风险等级: {risk['level']}\n"
                    f"主要风险: {risk['factors'][0] if risk['factors'] else '未知'}"
                )

            # 添加入场建议
            entry_info = ''
            if 'entry_targets' in signal:
                targets = signal['entry_targets']
                if targets['entry']:
                    entry_info = f"\n📍 建议入场区间: {' - '.join([f'{p:.2f}' for p in targets['entry']])}"
                if targets['stop_loss']:
                    entry_info += f"\n🛑 止损位: {targets['stop_loss']:.2f}"
                if targets['take_profit']:
                    entry_info += f"\n🎯 目标位: {' -> '.join([f'{p:.2f}' for p in targets['take_profit']])}"

            message = self.telegram.format_signal_message(
                symbol=signal_data['symbol'],
                signal_type=signal['type'],
                current_price=signal_data['price'],
                signal_score=signal['score'],
                technical_scores=', '.join(scores_text),
                trend_alignment=signal.get('trend_alignment', ''),
                volume_data=volume_data,
                risk_level=signal.get('risk_level', 'medium'),
                reason=signal.get('reason', ''),
                additional_info=f'{cycle_info}{risk_info}{entry_info}',
            )

            self.telegram.send_message(message)

    def _send_batch_telegram_alerts(self, batch_signals: List[Dict]):
        """改进的批量信号推送，包含形态分析信息"""
        if not self.telegram:
            return

        for signal in batch_signals:
            if signal['signal_type'] in [
                'buy',
                'sell',
                'strong_buy',
                'strong_sell',
            ]:
                # 构建详细消息
                technical_scores = signal.get('technical_score', {})
                scores_text = []
                if technical_scores:
                    if '4h' in technical_scores:
                        scores_text.append(f"4h:{technical_scores['4h']:.1f}")
                    if '1h' in technical_scores:
                        scores_text.append(f"1h:{technical_scores['1h']:.1f}")
                    if '15m' in technical_scores:
                        scores_text.append(
                            f"15m:{technical_scores['15m']:.1f}"
                        )

                # 添加形态信息
                patterns_text = ''
                if signal.get('patterns'):
                    patterns_text = (
                        f"\n📊 关键形态: {', '.join(signal['patterns'])}"
                    )

                message = self.telegram.format_signal_message(
                    symbol=signal['symbol'],
                    signal_type=signal['signal_type'],
                    current_price=signal['price'],
                    signal_score=signal['score'],
                    technical_scores=', '.join(scores_text),
                    trend_alignment=signal.get('trend_alignment', ''),
                    volume_data=signal['volume_data'],
                    risk_level=signal['risk_level'],
                    reason=signal['reason'],
                    additional_info=patterns_text,
                )

                self.telegram.send_message(message)

    def _format_kline_data(self, row) -> Dict:
        """格式化K线数据"""
        return {
            'open_time': row['Close time'],
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume']),
        }

    def start_monitoring(self):
        """启动市场监控"""
        print('正在启动市场监控...')

        self._initialize_data()
        self.running.set()

        # 启动所有监控线程
        threads = [
            ('Analysis', self._analysis_loop),
            ('Level Updates', self._periodic_update_levels),
        ]

        for name, target in threads:
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            print(f'✅ Started {name} thread')

        print('🚀 监控系统已启动')

    def stop(self):
        """Stop market monitoring"""
        print('正在停止监控...')
        self.running.clear()
        print('监控已停止')
