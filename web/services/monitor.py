import pandas as pd
import numpy as np
import talib
import websocket
import json
import threading
import time
import os
import queue
from itertools import chain
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from services.scan import MarketScanner
from analysis.data_fetcher import DataFetcher
from analysis.crypto_analyzer import CryptoAnalyzer
from analysis.technical_analyzer import TechnicalAnalyzer
from services.notifier import TelegramNotifier

from dotenv import load_dotenv

load_dotenv()


class MarketMonitor:
    def __init__(self, symbols: List[str] = [], use_proxy: bool = False):
        self.base_url = 'https://api.binance.com/api/v3'
        self.ws_url = 'wss://stream.binance.com:443/stream?streams='
        self.proxies = (
            {'http': 'http://127.0.0.1:1088', 'https': 'http://127.0.0.1:1088'}
            if use_proxy
            else None
        )

        self.user_define_symbols = [s.lower() for s in symbols]
        self.symbols = self.user_define_symbols
        self.kline_buffers = {
            symbol: deque(maxlen=100) for symbol in self.symbols
        }
        self.kline_data_buffers = {}
        self.volume_buffers = {
            symbol: deque(maxlen=20) for symbol in self.symbols
        }
        self.key_levels = {}
        self.latest_data = {}
        self.last_alert_time = {}

        # 添加消息队列
        self.message_queue = queue.Queue()

        # 添加事件标志
        self.running = threading.Event()
        self.ws = None

        # 添加锁
        self.data_lock = threading.Lock()
        # 添加scanner
        self.scanner = MarketScanner()
        # 新增: 添加技术分析器
        self.technical_analyzer = TechnicalAnalyzer()

        # Telegram配置
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

        # 添加Telegram通知服务
        self.telegram = None
        if telegram_token and telegram_chat_id:
            try:
                self.telegram = TelegramNotifier(
                    telegram_token, telegram_chat_id
                )
            except Exception as e:
                print(f'初始化Telegram通知服务失败: {e}')

    def update_monitoring_list(self):
        """更新监控列表"""
        try:
            print('正在更新监控列表...')
            top_symbols = self.scanner.get_top_symbols(top_n=10)

            # 合并所有列表并去重
            all_symbols = set()
            for category in ['volume', 'gainers', 'losers']:
                if category in top_symbols:
                    all_symbols.update(top_symbols[category])

            # 转换为小写并更新
            new_symbols = [s.lower() for s in all_symbols]

            # 打印监控列表变化
            added = set(new_symbols) - set(self.symbols)
            removed = set(self.symbols) - set(new_symbols)

            if added:
                print(f"新增监控: {', '.join(added)}")
            if removed:
                print(f"移除监控: {', '.join(removed)}")

            # 更新监控列表
            self.symbols = new_symbols

            # 更新数据结构
            with self.data_lock:
                # 添加新的缓冲区
                for symbol in added:
                    self.kline_buffers[symbol] = deque(maxlen=100)
                    self.volume_buffers[symbol] = deque(maxlen=20)

                # 移除旧的缓冲区
                for symbol in removed:
                    self.kline_buffers.pop(symbol, None)
                    self.volume_buffers.pop(symbol, None)
                    self.key_levels.pop(symbol, None)
                    self.latest_data.pop(symbol, None)
                    self.last_alert_time.pop(symbol, None)

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
                        symbol.upper()
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
                    else:
                        klines = DataFetcher.get_kline_data(
                            symbol.upper(), '1m', 1, limit=100
                        )
                        for _, row in klines.iterrows():
                            self.kline_buffers[symbol].append(
                                {
                                    'open_time': row['Close time'],
                                    'open': float(row['Open']),
                                    'high': float(row['High']),
                                    'low': float(row['Low']),
                                    'close': float(row['Close']),
                                    'volume': float(row['Volume']),
                                }
                            )
                    print(f'初始化{symbol}阻力位、支撑位为:{self.key_levels[symbol]}')
            except Exception as e:
                print(f'初始化{symbol}数据失败: {e}')

            # finally:
            #     import time

            # time.sleep(1)

        self.symbols = [x for x in self.symbols if x not in symbols_to_remove]

    def _start_websocket(self):
        """启动WebSocket连接"""

        def on_message(ws, message):
            if self.running.is_set():
                self.message_queue.put(message)

        def on_error(ws, error):
            print(f'WebSocket错误: {error}')
            self._reconnect()

        def on_close(ws, close_status_code, close_msg):
            print(f'WebSocket连接关闭: {close_status_code} - {close_msg}')
            self._reconnect()

        def on_open(ws):
            print('WebSocket连接已建立')

        # 准备订阅的streams
        streams = []
        for symbol in self.symbols:
            streams.extend(
                [f'{symbol}@kline_5m', f'{symbol}@depth5@1000ms']  # 改为1秒更新一次
            )

        ws_url = f"{self.ws_url}{'/'.join(streams)}"

        while self.running.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open,
                )

                self.ws.run_forever()
            except Exception as e:
                print(f'WebSocket连接异常: {e}')
                time.sleep(5)  # 重连前等待

    def _process_messages(self):
        """处理WebSocket消息"""
        while self.running.is_set():
            try:
                # 使用超时获取消息，避免阻塞
                message = self.message_queue.get(timeout=1)
                data = json.loads(message)

                if 'stream' in data:
                    if 'kline' in data['stream']:
                        self._handle_kline_data(data['data'])
                    elif 'depth' in data['stream']:
                        self._handle_depth_data(data['data'], data['stream'])

            except queue.Empty:
                continue
            except Exception as e:
                print(f'处理消息出错: {e}')
                time.sleep(0.1)  # 添加小延迟

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
                            symbol
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

    def _handle_kline_data(self, data):
        """处理K线数据"""
        try:
            symbol = data['s'].lower()
            kline = data['k']

            # 使用锁保护数据更新
            with self.data_lock:
                # 更新K线缓存
                self.kline_buffers[symbol].append(
                    {
                        'open_time': datetime.fromtimestamp(
                            int(kline['t']) / 1000
                        ),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v']),
                    }
                )

                # 更新最新数据
                self.latest_data[symbol] = {
                    'price': float(kline['c']),
                    'volume': float(kline['v']),
                }

        except Exception as e:
            print(f'处理K线数据失败: {e}')

    def _handle_depth_data(self, data, symbol):
        """处理深度数据"""
        try:

            # 计算买卖压力
            bid_volume = sum(float(bid[1]) for bid in data['bids'][:5])
            ask_volume = sum(float(ask[1]) for ask in data['asks'][:5])

            # 使用锁保护数据更新
            with self.data_lock:
                # 更新量能缓存
                self.volume_buffers[symbol.split('@')[0]].append(
                    {
                        'time': datetime.now(),
                        'bid_volume': bid_volume,
                        'ask_volume': ask_volume,
                    }
                )

        except Exception as e:
            print(f'处理深度数据失败: {e}')

    def _generate_action_guide(
        self,
        signal_type: str,
        risk_level: str,
        price_eval: Dict,
        volume_eval: Dict,
    ) -> str:
        """生成详细的操作建议"""
        try:
            price_position = price_eval['details']['relative_position']
            volume_ratio = volume_eval['details']['volume_ratio']

            if risk_level == 'high':
                if price_position > 0.8:
                    return '建议观望，等待回调'
                elif volume_ratio > 5:
                    return '建议观望或谨慎小仓试探'
                else:
                    return '建议谨慎，可少量试仓'

            elif risk_level == 'medium':
                if signal_type in ['strong_buy', 'buy']:
                    return '建议分批建仓，首仓20%'
                else:
                    return '建议观望或谨慎操作'

            else:
                if signal_type == 'strong_buy':
                    return '可以考虑分批建仓，首仓30%'
                elif signal_type == 'buy':
                    return '可以考虑少量建仓'

            return '建议观望，等待更好的机会'

        except Exception as e:
            print(f'生成操作建议失败: {e}')
            return '建议观望，等待更好的机会'

    def _assess_comprehensive_risk(
        self, price_eval: Dict, volume_eval: Dict, adjusted_score: float
    ) -> str:
        """综合风险评估"""
        try:
            # 提取关键指标
            price_risk = price_eval['risk_level']
            volume_risk = volume_eval['risk_level']
            price_position = price_eval['details']['relative_position']
            volatility = price_eval['details']['volatility']
            volume_ratio = volume_eval['details']['volume_ratio']

            # 高风险情况
            high_risk_conditions = [
                price_position > 0.85,  # 价格极高位
                volatility > 0.08,  # 波动率极高
                volume_ratio > 10,  # 成交量暴涨
                price_risk == 'high' and volume_risk == 'high',
            ]

            # 中等风险情况
            medium_risk_conditions = [
                0.7 < price_position < 0.85,  # 价格高位
                0.05 < volatility < 0.08,  # 波动率较高
                5 < volume_ratio < 10,  # 成交量放大明显
                price_risk == 'medium' or volume_risk == 'medium',
            ]

            if any(high_risk_conditions):
                return 'high'
            elif any(medium_risk_conditions):
                return 'medium'
            else:
                return 'low'

        except Exception as e:
            print(f'评估综合风险失败: {e}')
            return 'high'

    def _generate_signal(
        self,
        signal_scores: Dict,
        current_price: float,
        price_eval: Dict,
        volume_eval: Dict,
        symbol: str,
    ) -> Optional[Dict]:
        """优化后的信号生成逻辑"""
        try:
            final_score = signal_scores['final_score']
            # components = signal_scores.get('components', {})

            # 1. 价格位置评分
            price_score = price_eval['score']
            price_position = price_eval['details']['relative_position']
            price_volatility = price_eval['details']['volatility']

            # 2. 成交量评分
            volume_score = volume_eval['score']
            volume_ratio = volume_eval['details']['volume_ratio']
            pressure_ratio = volume_eval['details']['pressure_ratio']

            # 3. 计算调整后的信号分数
            adjusted_score = final_score

            # 根据价格位置调整
            if price_position > 0.8:  # 价格在高位
                adjusted_score *= 0.8
                if price_volatility > 0.05:  # 高位波动大
                    adjusted_score *= 0.9

            # 根据成交量异常程度调整
            if volume_ratio > 5:  # 成交量过度放大
                if pressure_ratio < 1:  # 卖压大于买压
                    adjusted_score *= 0.85
                elif pressure_ratio > 3:  # 买压远大于卖压
                    adjusted_score *= 0.9  # 可能是爆拉

            # 4. 确定信号类型
            if (
                adjusted_score >= 80
                and volume_score >= 70
                and price_score >= 60
            ):
                signal_type = 'strong_buy'
            elif adjusted_score >= 65:
                signal_type = 'buy'
            elif adjusted_score <= 20 and volume_score <= 30:
                signal_type = 'strong_sell'
            elif adjusted_score <= 35:
                signal_type = 'sell'
            else:
                return None

            # 5. 评估风险等级
            risk_level = self._assess_comprehensive_risk(
                price_eval, volume_eval, adjusted_score
            )

            # 6. 生成原因说明
            reasons = []

            if volume_ratio > 2:
                reasons.append(f'量比: {volume_ratio:.2f}')
            if pressure_ratio > 1.2 or pressure_ratio < 0.8:
                reasons.append(f'买卖比: {pressure_ratio:.2f}')

            # 添加价格相关原因
            if price_position > 0.7:
                reasons.append('价格处于高位')
            elif price_position < 0.3:
                reasons.append('价格处于低位')

            if price_volatility > 0.05:
                reasons.append('波动率偏高')

            # 7. 生成操作建议
            action_guide = self._generate_action_guide(
                signal_type, risk_level, price_eval, volume_eval
            )

            return {
                'symbol': symbol,
                'type': signal_type,
                'score': adjusted_score,
                'price': current_price,
                'risk_level': risk_level,
                'reasons': reasons,
                'action_guide': action_guide,
            }

        except Exception as e:
            print(f'生成信号失败: {e}')
            return None

    def _analyze_trend(self, ma_data: Dict) -> Dict:
        """分析均线趋势"""
        try:
            ma5 = ma_data.get(5, 0)
            ma10 = ma_data.get(10, 0)
            ma20 = ma_data.get(20, 0)
            ma50 = ma_data.get(50, 0)

            # 计算方向
            if ma5 > ma10 > ma20:
                direction = 'up'
                strength = (ma5 / ma20 - 1) * 100  # 计算偏离度
            elif ma5 < ma10 < ma20:
                direction = 'down'
                strength = (1 - ma5 / ma20) * 100
            else:
                direction = 'neutral'
                strength = 0

            # 计算趋势强度
            trend_score = 0
            if direction == 'up':
                if ma5 > ma10 > ma20 > ma50:
                    trend_score = 100  # 最强趋势
                elif ma5 > ma10 > ma20:
                    trend_score = 75
                elif ma5 > ma10:
                    trend_score = 50
            elif direction == 'down':
                if ma5 < ma10 < ma20 < ma50:
                    trend_score = 0  # 最弱趋势
                elif ma5 < ma10 < ma20:
                    trend_score = 25
                elif ma5 < ma10:
                    trend_score = 40
            else:
                trend_score = 50  # 盘整

            return {
                'direction': direction,
                'strength': abs(strength),
                'score': trend_score,
                'ma5': ma5,
                'ma20': ma20,
                'ma50': ma50,
            }

        except Exception as e:
            print(f'分析趋势失败: {e}')
            return {'direction': 'neutral', 'strength': 0, 'score': 50}

    def _analyze_patterns(self, patterns: Dict) -> float:
        """分析形态得分"""
        try:
            score = 50  # 基础分

            # 处理双顶/双底
            if patterns.get('double_bottom', False):
                score += 20
            if patterns.get('double_top', False):
                score -= 20

            # 处理趋势强度
            trend = patterns.get('trend', {})
            trend_strength = trend.get('strength', 'neutral')

            if trend_strength == 'strong_up':
                score += 25
            elif trend_strength == 'weak_up':
                score += 15
            elif trend_strength == 'strong_down':
                score -= 25
            elif trend_strength == 'weak_down':
                score -= 15

            return max(0, min(100, score))

        except Exception as e:
            print(f'分析形态失败: {e}')
            return 50

    def _analyze_rsi(self, rsi_1h: float, rsi_15m: float) -> float:
        """分析RSI得分"""
        try:
            # 评估1小时RSI
            if rsi_1h < 30:
                score_1h = 100 - (30 - rsi_1h) * 2  # 过度超卖给较低分
            elif rsi_1h > 70:
                score_1h = 100 - (rsi_1h - 70) * 2  # 过度超买给较低分
            elif 40 <= rsi_1h <= 60:
                score_1h = 50  # 中性区间
            else:
                score_1h = 75  # 健康区间

            # 评估15分钟RSI
            if rsi_15m < 30:
                score_15m = 100 - (30 - rsi_15m) * 2
            elif rsi_15m > 70:
                score_15m = 100 - (rsi_15m - 70) * 2
            elif 40 <= rsi_15m <= 60:
                score_15m = 50
            else:
                score_15m = 75

            # 综合得分，1小时权重更大
            final_score = score_1h * 0.7 + score_15m * 0.3

            return max(0, min(100, final_score))

        except Exception as e:
            print(f'分析RSI失败: {e}')
            return 50

    def _analyze_macd(self, macd_1h: Dict, macd_15m: Dict) -> float:
        """分析MACD得分"""
        try:
            score = 50  # 基础分

            # 分析1小时MACD
            hist_1h = macd_1h.get('hist', 0)
            macd_1h_value = macd_1h.get('macd', 0)
            signal_1h = macd_1h.get('signal', 0)

            if hist_1h > 0:
                if macd_1h_value > signal_1h:  # MACD上穿信号线
                    score += 20
                score += min(20, hist_1h * 1000)  # 柱状图力度
            else:
                if macd_1h_value < signal_1h:  # MACD下穿信号线
                    score -= 20
                score -= min(20, abs(hist_1h * 1000))

            # 分析15分钟MACD
            hist_15m = macd_15m.get('hist', 0)
            macd_15m_value = macd_15m.get('macd', 0)
            signal_15m = macd_15m.get('signal', 0)

            if hist_15m > 0:
                if macd_15m_value > signal_15m:
                    score += 10
                score += min(10, hist_15m * 1000)
            else:
                if macd_15m_value < signal_15m:
                    score -= 10
                score -= min(10, abs(hist_15m * 1000))

            return max(0, min(100, score))

        except Exception as e:
            print(f'分析MACD失败: {e}')
            return 50

    def _get_rsi_status(self, rsi_1h: float, rsi_15m: float) -> str:
        """获取RSI状态"""
        try:
            if rsi_1h > 70 and rsi_15m > 70:
                return 'extreme_overbought'
            elif rsi_1h < 30 and rsi_15m < 30:
                return 'extreme_oversold'
            elif rsi_1h > 60 and rsi_15m > 60:
                return 'overbought'
            elif rsi_1h < 40 and rsi_15m < 40:
                return 'oversold'
            else:
                return 'neutral'
        except Exception as e:
            print(f'获取RSI状态失败: {e}')
            return 'neutral'

    def _get_macd_status(self, macd_1h: Dict, macd_15m: Dict) -> str:
        """获取MACD状态"""
        try:
            hist_1h = macd_1h.get('hist', 0)
            hist_15m = macd_15m.get('hist', 0)

            if hist_1h > 0 and hist_15m > 0:
                return 'strong_bullish'
            elif hist_1h < 0 and hist_15m < 0:
                return 'strong_bearish'
            elif hist_1h > 0:
                return 'bullish'
            elif hist_1h < 0:
                return 'bearish'
            else:
                return 'neutral'
        except Exception as e:
            print(f'获取MACD状态失败: {e}')
            return 'neutral'

    def _generate_signal_comment(self, signal_scores: Dict) -> str:
        """生成信号说明"""
        comments = []

        # 添加趋势相关说明
        if signal_scores['base_score'] > 60:
            comments.append('趋势强势')

        # 添加动量相关说明
        if signal_scores['momentum_score'] > 60:
            comments.append('动能强劲')

        # 添加成交量相关说明
        if signal_scores['volume_score'] > 60:
            comments.append('量能充足')

        return ' | '.join(comments)

    def _determine_signal_type(self, score: float) -> Optional[str]:
        """确定信号类型"""
        if score >= 75:
            return 'strong_buy'
        elif score >= 65:
            return 'buy'
        elif score <= 25:
            return 'strong_sell'
        elif score <= 35:
            return 'sell'
        return None

    def _evaluate_price_position(
        self, kline_data: List[Dict], current_price: float
    ) -> Dict:
        """
        评估价格位置
        return: Dict包含位置分数和具体信息
        """
        try:
            # 将K线数据转换为numpy数组
            prices = np.array([k['close'] for k in kline_data])
            highs = np.array([k['high'] for k in kline_data])
            lows = np.array([k['low'] for k in kline_data])

            # 1. 计算相对高低点位置
            highest = np.max(highs)
            lowest = np.min(lows)
            price_range = highest - lowest
            if price_range == 0:
                relative_position = 0.5
            else:
                relative_position = (current_price - lowest) / price_range

            # 2. 计算移动平均线位置
            ma20 = talib.SMA(prices, timeperiod=20)[-1]
            ma50 = talib.SMA(prices, timeperiod=50)[-1]

            # 3. 计算布林带位置
            upper, middle, lower = talib.BBANDS(
                prices, timeperiod=20, nbdevup=2, nbdevdn=2
            )
            bb_position = (current_price - lower[-1]) / (upper[-1] - lower[-1])

            # 4. 计算波动率
            atr = talib.ATR(highs, lows, prices, timeperiod=14)[-1]
            avg_price = np.mean(prices[-20:])
            volatility = atr / avg_price

            # 5. 价格趋势强度
            ema_fast = talib.EMA(prices, timeperiod=5)[-1]
            ema_slow = talib.EMA(prices, timeperiod=20)[-1]
            trend_strength = (ema_fast / ema_slow - 1) * 100

            # 综合评分 (0-100)
            position_score = 0

            # 根据相对位置打分
            if relative_position > 0.8:
                position_score += 20  # 接近历史高点
            elif relative_position < 0.2:
                position_score += 80  # 接近历史低点
            else:
                position_score += 50  # 中间区域

            # 根据均线位置调整
            if current_price > ma50 > ma20:
                position_score -= 10  # 下跌趋势
            elif current_price > ma20 > ma50:
                position_score += 10  # 上涨趋势

            # 根据布林带位置调整
            if bb_position > 0.8:
                position_score -= 15  # 接近上轨
            elif bb_position < 0.2:
                position_score += 15  # 接近下轨

            # 根据波动率调整
            if volatility > 0.05:  # 5%以上的日波动率considered高
                position_score -= 10

            # 确保分数在0-100范围内
            position_score = max(0, min(100, position_score))

            return {
                'score': position_score,
                'details': {
                    'relative_position': relative_position,
                    'bb_position': bb_position,
                    'volatility': volatility,
                    'trend_strength': trend_strength,
                    'price_ma20_ratio': current_price / ma20,
                    'price_ma50_ratio': current_price / ma50,
                },
                'risk_level': 'high'
                if position_score < 40
                else 'medium'
                if position_score < 70
                else 'low',
            }

        except Exception as e:
            print(f'评估价格位置失败: {e}')
            import traceback

            print(traceback.format_exc())
            return {'score': 50, 'details': {}, 'risk_level': 'high'}

    def _evaluate_volume_quality(self, volume_data: deque) -> Dict:
        """评估成交量质量"""
        try:
            # 将deque转换为列表便于处理
            volume_list = list(volume_data)
            if not volume_list:
                return {
                    'score': 50,
                    'details': {
                        'volume_ratio': 1,
                        'pressure_ratio': 1,
                        'volume_trend': 0,
                    },
                    'risk_level': 'medium',
                }

            # 计算最近5个周期的买卖量
            recent_bid_volume = sum(v['bid_volume'] for v in volume_list[-5:])
            recent_ask_volume = sum(v['ask_volume'] for v in volume_list[-5:])

            # 计算历史平均成交量(排除最近5个周期)
            historical_volumes = []
            for v in volume_list[:-5]:
                total_volume = v['bid_volume'] + v['ask_volume']
                if total_volume > 0:
                    historical_volumes.append(total_volume)

            current_volume = recent_bid_volume + recent_ask_volume
            avg_volume = (
                np.mean(historical_volumes)
                if historical_volumes
                else current_volume
            )

            # 计算关键指标
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            pressure_ratio = (
                recent_bid_volume / recent_ask_volume
                if recent_ask_volume > 0
                else 1
            )

            # 计算基础分数
            base_score = 50

            # 根据成交量比率调整分数
            if volume_ratio > 3:
                base_score += 20
            elif volume_ratio > 2:
                base_score += 10
            elif volume_ratio < 0.5:
                base_score -= 20

            # 根据买卖压力比调整分数
            if pressure_ratio > 1.5:
                base_score += 20
            elif pressure_ratio > 1.2:
                base_score += 10
            elif pressure_ratio < 0.8:
                base_score -= 10
            elif pressure_ratio < 0.5:
                base_score -= 20

            # 确保分数在0-100范围内
            final_score = max(0, min(100, base_score))

            # 评估风险等级
            if final_score >= 70 and pressure_ratio > 1.2:
                risk_level = 'low'
            elif final_score <= 30 or pressure_ratio < 0.5:
                risk_level = 'high'
            else:
                risk_level = 'medium'

            return {
                'score': final_score,
                'details': {
                    'volume_ratio': volume_ratio,
                    'pressure_ratio': pressure_ratio,
                },
                'risk_level': risk_level,
            }

        except Exception as e:
            print(f'评估成交量质量失败: {e}')
            return {
                'score': 50,
                'details': {
                    'volume_ratio': 1,
                    'pressure_ratio': 1,
                },
                'risk_level': 'high',
            }

    def _calculate_position_risk(self, price_eval: Dict) -> float:
        """计算价格位置风险分数"""
        try:
            # 从价格评估结果中提取相对位置
            price_position = price_eval.get('details', {}).get(
                'relative_position', 0.5
            )

            if isinstance(price_position, (int, float)):
                if price_position > 0.8:
                    return 80  # 高位风险大
                elif price_position > 0.7:
                    return 60
                elif price_position < 0.2:
                    return 30  # 低位风险小
                elif price_position < 0.3:
                    return 40
                else:
                    return 50  # 中间位置适中风险
            return 50

        except Exception as e:
            print(f'计算位置风险失败: {e}')
            return 50

    def _assess_risk_level(self, signal_scores: Dict, symbol: str) -> str:
        """进一步细化风险评估"""
        try:
            components = signal_scores.get('components', {})

            # 1. 基础风险评估
            # structure_score = components.get('structure', 50)
            momentum_score = components.get('momentum', 50)
            # volume_score = components.get('volume', 50)

            # 2. 价格位置评估
            price_position = self._evaluate_price_position(
                self._convert_df_to_list(
                    self.kline_data_buffers[symbol]['kline_data_1h']
                ),
                self.kline_data_buffers[symbol]['current_price'],
            )

            # 3. 成交量质量评估
            volume_quality = self._evaluate_volume_quality(
                self.volume_buffers[symbol]
            )

            # 4. 综合风险评估
            risk_score = (
                self._calculate_position_risk(price_position) * 0.4
                + self._calculate_momentum_risk(momentum_score) * 0.3
                + self._calculate_volume_risk(volume_quality) * 0.3
            )

            # 5. 风险等级判定
            if risk_score < 30:
                return 'low'
            elif risk_score < 60:
                return 'medium'
            else:
                return 'high'

        except Exception as e:
            print(f'评估风险失败: {e}')
            return 'high'

    def _generate_signals(
        self,
        symbol: str,
        price: float,
        volume_ratio: float,
        volume_surge: bool,
        current_time: datetime,
    ):
        """生成交易信号"""
        try:
            # 检查最后提醒时间
            if symbol in self.last_alert_time:
                if (
                    current_time - self.last_alert_time[symbol]
                ).total_seconds() < 60:
                    return

            signals = []
            key_levels = self.key_levels.get(symbol, {})
            if not key_levels:
                return

            # 生成信号逻辑...
            support_levels = key_levels.get('supports', [])
            resistance_levels = key_levels.get('resistances', [])

            # 支撑位信号
            for support in support_levels:
                if 0.995 <= price / support <= 1.005:
                    strength = (
                        'strong'
                        if volume_ratio > 1.2 and volume_surge
                        else 'medium'
                    )
                    signals.append(
                        {
                            'type': 'buy',
                            'strength': strength,
                            'reason': f'价格接近支撑位 {support:.2f}, 买盘压力{"强" if strength == "strong" else "一般"}',
                        }
                    )

            # 阻力位信号
            for resistance in resistance_levels:
                if 0.995 <= price / resistance <= 1.005:
                    strength = (
                        'strong'
                        if volume_ratio < 0.8 and volume_surge
                        else 'medium'
                    )
                    signals.append(
                        {
                            'type': 'sell',
                            'strength': strength,
                            'reason': f'价格接近阻力位 {resistance:.2f}, 卖盘压力{"强" if strength == "strong" else "一般"}',
                        }
                    )

            # 输出信号
            if signals:
                print(f'\n=== {symbol.upper()} 信号提醒 ===')
                print(f"时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f'当前价格: {price:.2f}')
                print(f'买卖量比: {volume_ratio:.2f}')

                for signal in signals:
                    strength_stars = '★' * (
                        2 if signal['strength'] == 'strong' else 1
                    )
                    print(
                        f"{signal['type'].upper()} {strength_stars}: {signal['reason']}"
                    )

                self.last_alert_time[symbol] = current_time

        except Exception as e:
            print(f'生成信号失败: {e}')
            import traceback

            print(traceback.format_exc())

    def _reconnect(self):
        """重新连接WebSocket"""
        if self.running.is_set():
            print('正在尝试重新连接...')
            time.sleep(5)  # 等待5秒后重连
            threading.Thread(target=self._start_websocket).start()

    def _analysis_loop(self):
        """分析循环"""
        while self.running.is_set():
            try:
                current_time = datetime.now()
                # 每个交易对单独处理
                for symbol in self.symbols:
                    with self.data_lock:

                        if symbol in self.latest_data:
                            self._analyze_symbol(symbol, current_time)

                # 添加适当的延迟，避免过于频繁的分析
                time.sleep(10)

            except Exception as e:
                print(f'分析过程出错: {e}')
                time.sleep(0.1)

    def _prepare_kline_data(
        self, symbol: str, interval: str, days: int
    ) -> pd.DataFrame:
        """获取并预处理K线数据"""
        try:
            # 获取K线数据
            df = DataFetcher.get_kline_data(symbol.upper(), interval, days)

            # 确保数据类型正确
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col])

            return df

        except Exception as e:
            print(f'获取{interval}数据失败: {e}')
            return pd.DataFrame()

    def _convert_df_to_list(self, df: pd.DataFrame) -> List[Dict]:
        """将DataFrame转换为列表格式"""
        return [
            {
                'open_time': row.name,
                'open': row['Open'],
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                'volume': row['Volume'],
            }
            for _, row in df.iterrows()
        ]

    def _calculate_timeframe_indicators(
        self, df: pd.DataFrame, timeframe: str
    ) -> Dict:
        """计算指定时间周期的技术指标"""
        try:
            converted_data = self._convert_df_to_list(df)
            return {
                'timeframe': timeframe,
                'indicators': self.technical_analyzer.calculate_indicators(
                    converted_data
                ),
            }
        except Exception as e:
            print(f'计算{timeframe}指标失败: {e}')
            return {'timeframe': timeframe, 'indicators': {}}

    def _analyze_symbol(self, symbol: str, current_time: datetime):
        """多时间周期分析"""
        try:
            current_price = self.latest_data[symbol]['price']

            # 1. 获取多时间周期K线数据
            kline_data_1h = self._prepare_kline_data(
                symbol, '1h', 7
            )  # 7天的1小时数据
            kline_data_15m = self._prepare_kline_data(
                symbol, '15m', 1
            )  # 1天的15分钟数据
            self.kline_data_buffers[symbol] = {
                'current_price': current_price,
                'kline_data_1h': kline_data_1h,
                'kline_data_15m': kline_data_15m,
            }
            if len(kline_data_1h) < 50 or len(kline_data_15m) < 20:  # 确保数据充足
                return

            # 2. 评估价格位置
            price_eval = self._evaluate_price_position(
                self._convert_df_to_list(kline_data_1h), current_price
            )

            # 3. 评估成交量 - 直接传递volume_buffers中的deque
            volume_eval = self._evaluate_volume_quality(
                self.volume_buffers[symbol]
            )

            # 2. 分别计算两个时间周期的技术指标
            indicators_1h = self._calculate_timeframe_indicators(
                kline_data_1h, '1h'
            )
            indicators_15m = self._calculate_timeframe_indicators(
                kline_data_15m, '15m'
            )

            # 3. 分析形态
            patterns_1h = self.technical_analyzer.analyze_price_pattern(
                self._convert_df_to_list(kline_data_1h)
            )
            patterns_15m = self.technical_analyzer.analyze_price_pattern(
                self._convert_df_to_list(kline_data_15m)
            )

            # 4. 获取成交量数据
            volume_data = {}
            if len(self.volume_buffers[symbol]) >= 5:
                volume_data = self._prepare_volume_data(symbol)
            # 5. 生成综合信号
            signals = self._generate_combined_signals(
                symbol=symbol,
                current_price=current_price,
                indicators_1h=indicators_1h,
                indicators_15m=indicators_15m,
                patterns_1h=patterns_1h,
                patterns_15m=patterns_15m,
                volume_data=volume_data,
                price_eval=price_eval,
                volume_eval=volume_eval,
            )

            # 7. 输出信号
            volume_data = {
                'ratio': volume_eval['details']['volume_ratio'],
                'pressure_ratio': volume_eval['details']['pressure_ratio'],
            }

            # 6. 输出信号
            self._output_signals(
                symbol, signals, current_time, current_price, volume_data
            )

        except Exception as e:
            print(f'分析{symbol}时出错: {e}')
            import traceback

            print(traceback.format_exc())

    def _generate_combined_signals(
        self,
        symbol: str,
        current_price: float,
        indicators_1h: Dict,
        indicators_15m: Dict,
        patterns_1h: Dict,
        patterns_15m: Dict,
        volume_data: Dict,
        price_eval: Dict,
        volume_eval: Dict,
    ) -> List[Dict]:
        """生成综合信号"""
        signals = []

        try:
            # 1. 计算各维度得分
            score_1h = self.technical_analyzer._calculate_technical_score(
                indicators_1h['indicators']
            )
            pattern_score_1h = (
                self.technical_analyzer._calculate_pattern_score(patterns_1h)
            )
            score_15m = self.technical_analyzer._calculate_technical_score(
                indicators_15m['indicators']
            )
            pattern_score_15m = (
                self.technical_analyzer._calculate_pattern_score(patterns_15m)
            )

            # 2. 获取价格和成交量评估结果
            price_score = price_eval['score']
            volume_score = volume_eval['score']

            # 3. 计算综合得分
            total_score = (
                score_1h * 0.3
                + score_15m * 0.2
                + pattern_score_1h * 0.1
                + pattern_score_15m * 0.1
                + price_score * 0.15
                + volume_score * 0.15
            )

            # 4. 生成信号
            if signal := self._generate_signal(
                {'final_score': total_score},
                current_price,
                price_eval,
                volume_eval,
                symbol,
            ):
                signals.append(signal)

            return signals

        except Exception as e:
            print(f'生成信号失败: {e}')
            return []

    def _get_indicators(
        self, indicators_1h: Dict, indicators_15m: Dict
    ) -> Dict:
        """整理技术指标"""
        return {
            'rsi_1h': indicators_1h['indicators'].get('rsi', 50),
            'rsi_15m': indicators_15m['indicators'].get('rsi', 50),
            'macd_1h': indicators_1h['indicators'].get('macd', {}),
            'macd_15m': indicators_15m['indicators'].get('macd', {}),
            'ma_1h': indicators_1h['indicators'].get('ma', {}),
            'ma_15m': indicators_15m['indicators'].get('ma', {}),
            'bb_1h': indicators_1h['indicators'].get('bollinger', {}),
            'bb_15m': indicators_15m['indicators'].get('bollinger', {}),
        }

    def _analyze_market_structure(
        self, ma_1h: Dict, ma_15m: Dict, patterns_1h: Dict, patterns_15m: Dict
    ) -> Dict:
        """优化后的市场结构分析"""
        try:
            # 1. 趋势分析
            trend_1h = self._analyze_trend(ma_1h)
            trend_15m = self._analyze_trend(ma_15m)

            # 2. 趋势得分
            trend_score = trend_1h['score'] * 0.7 + trend_15m['score'] * 0.3

            # 3. 形态得分
            pattern_score = (
                self._analyze_patterns(patterns_1h) * 0.7
                + self._analyze_patterns(patterns_15m) * 0.3
            )

            # 4. 趋势一致性检查
            trend_aligned = trend_1h['direction'] == trend_15m['direction']
            if not trend_aligned:
                trend_score *= 0.7  # 趋势不一致降分

            # 5. 综合得分
            structure_score = trend_score * 0.6 + pattern_score * 0.4

            return {
                'trend_1h': trend_1h,
                'trend_15m': trend_15m,
                'pattern_score': pattern_score,
                'trend_aligned': trend_aligned,
                'structure_score': min(100, structure_score),  # 确保不超过100
            }
        except Exception as e:
            print(f'分析市场结构失败: {e}')
            return {'structure_score': 50}

    def _analyze_momentum(
        self, rsi_1h: float, rsi_15m: float, macd_1h: Dict, macd_15m: Dict
    ) -> Dict:
        """优化后的动量分析"""
        try:
            # 1. RSI分析
            rsi_score = self._analyze_rsi(rsi_1h, rsi_15m)

            # 2. MACD分析
            macd_score = self._analyze_macd(macd_1h, macd_15m)

            # 3. RSI过热检查
            if rsi_1h > 75 or rsi_15m > 75:
                rsi_score *= 0.5  # RSI过热大幅降分
            elif rsi_1h > 70 or rsi_15m > 70:
                rsi_score *= 0.7  # RSI偏热适度降分

            # 4. 动量一致性检查
            momentum_aligned = (rsi_score > 50 and macd_score > 50) or (
                rsi_score < 50 and macd_score < 50
            )
            if not momentum_aligned:
                rsi_score *= 0.8
                macd_score *= 0.8

            # 5. 计算最终动量强度
            momentum_strength = rsi_score * 0.5 + macd_score * 0.5

            return {
                'rsi_score': rsi_score,
                'macd_score': macd_score,
                'momentum_strength': min(100, momentum_strength),  # 确保不超过100
                'rsi_status': self._get_rsi_status(rsi_1h, rsi_15m),
                'macd_status': self._get_macd_status(macd_1h, macd_15m),
            }
        except Exception as e:
            print(f'分析动量失败: {e}')
            return {'momentum_strength': 50}

    def _analyze_volume_profile(self, volume_data: Dict) -> Dict:
        """分析成交量特征"""
        try:
            volume_ratio = volume_data.get('ratio', 1)
            bid_volume = volume_data.get('bid_volume', 0)
            ask_volume = volume_data.get('ask_volume', 1)

            # 计算买卖压力比
            pressure_ratio = bid_volume / ask_volume if ask_volume > 0 else 1

            # 评估成交量强度
            volume_strength = min(volume_ratio / 2, 1) * 50  # 标准化到0-50

            # 评估买卖压力
            pressure_strength = min(pressure_ratio / 2, 1) * 50  # 标准化到0-50

            return {
                'volume_ratio': volume_ratio,
                'pressure_ratio': pressure_ratio,
                'volume_strength': volume_strength,
                'pressure_strength': pressure_strength,
                'volume_score': (volume_strength + pressure_strength) / 2,
            }
        except Exception as e:
            print(f'分析成交量失败: {e}')
            return {'volume_score': 0}

    def _calculate_signal_scores(
        self, market_structure: Dict, momentum: Dict, volume_profile: Dict
    ) -> Dict:
        """修复后的信号得分计算"""
        try:
            # 1. 市场结构得分 (0-100)
            structure_score = market_structure.get('structure_score', 50)

            # 2. 动量得分 (0-100)
            momentum_score = momentum.get('momentum_strength', 50)

            # 3. 成交量得分 (0-100)
            volume_score = volume_profile.get('volume_score', 50)

            # 4. 计算最终得分(归一化到0-100)
            final_score = (
                structure_score * 0.4
                + momentum_score * 0.4  # 市场结构权重
                + volume_score * 0.2  # 动量指标权重  # 成交量权重
            )

            return {
                'final_score': min(100, final_score),  # 确保不超过100
                'components': {
                    'structure': structure_score,
                    'momentum': momentum_score,
                    'volume': volume_score,
                },
            }
        except Exception as e:
            print(f'计算信号得分失败: {e}')
            return {'final_score': 50}

    def _output_signals(
        self,
        symbol: str,
        signals: List[Dict],
        current_time: datetime,
        current_price: float,
        volume_data: Dict,
    ):
        """输出交易信号"""
        if not signals:
            return

        # 检查最后提醒时间
        if symbol in self.last_alert_time:
            if (
                current_time - self.last_alert_time[symbol]
            ).total_seconds() < 300:  # 5分钟内不重复提醒
                return

        print(f'\n{"="*50}')
        print(
            f'交易对: {symbol.upper()} - 时间: {current_time.strftime("%Y-%m-%d %H:%M:%S")}'
        )
        print(f'当前价格: {current_price:.8f}')

        # 输出成交量信息
        if volume_data:
            if 'ratio' in volume_data:
                print(f'成交量比率: {volume_data["ratio"]:.2f}')
            if 'pressure_ratio' in volume_data:
                print(f'买卖比: {volume_data["pressure_ratio"]:.2f}')

        # 输出信号
        for signal in signals:
            signal_type_map = {
                'strong_buy': '🔥🔥🔥 强力买入',
                'buy': '📈 买入',
                'sell': '📉 卖出',
                'strong_sell': '❄️❄️❄️ 强力卖出',
            }
            signal_type = signal_type_map.get(signal['type'], '🔍 观察')

            print(f'\n信号类型: {signal_type}')
            print(f"信号强度: {signal['score']:.1f}/100")
            print(f"风险等级: {signal['risk_level']}")

            # 输出触发原因
            reasons = []
            if volume_data.get('ratio', 0) > 1.5:
                reasons.append(f"量比: {volume_data['ratio']:.2f}")
            if (
                volume_data.get('pressure_ratio', 0) > 1.2
                or volume_data.get('pressure_ratio', 0) < 0.8
            ):
                reasons.append(f"买卖比: {volume_data['pressure_ratio']:.2f}")

            if signal.get('reasons'):
                reasons.extend(signal['reasons'])

            if reasons:
                print(f"触发原因: {' | '.join(reasons)}")

            # 输出操作建议
            if 'action_guide' in signal:
                print(f"操作建议: {signal['action_guide']}")

        import pdb

        pdb.set_trace()
        # 发送Telegram通知
        if self.telegram and any(
            signal['type'] in ['buy', 'strong_buy', 'strong_sell']
            for signal in signals
        ):
            for signal in signals:
                if signal['type'] in ['buy', 'strong_buy', 'strong_sell']:
                    message = self.telegram.format_signal_message(
                        symbol=symbol,
                        signal_type=signal['type'],
                        current_price=current_price,
                        signal_score=signal['score'],
                        risk_level=signal['risk_level'],
                        volume_data=volume_data,
                        reasons=signal.get('reasons', []),
                        action_guide=signal.get('action_guide'),
                    )
                    self.telegram.send_message(message)
        # 更新最后提醒时间
        self.last_alert_time[symbol] = current_time
        print(f'{"="*50}\n')

    def _calculate_momentum_risk(self, momentum_score: float) -> float:
        """计算动量风险分数"""
        try:
            if momentum_score > 80:
                return 70  # 过热风险
            elif momentum_score > 70:
                return 60
            elif momentum_score < 20:
                return 40  # 超卖风险较小
            elif momentum_score < 30:
                return 45
            else:
                return 50

        except Exception as e:
            print(f'计算动量风险失败: {e}')
            return 50

    def _calculate_volume_risk(self, volume_quality: Dict) -> float:
        """计算成交量风险分数"""
        try:
            volume_ratio = volume_quality.get('volume_ratio', 1)
            pressure_ratio = volume_quality.get('pressure_ratio', 1)

            # 基础风险分数
            risk_score = 50

            # 成交量异常程度
            if volume_ratio > 5:
                risk_score += 30
            elif volume_ratio > 3:
                risk_score += 20
            elif volume_ratio > 2:
                risk_score += 10

            # 买卖压力不平衡
            if pressure_ratio > 3:
                risk_score += 20
            elif pressure_ratio > 2:
                risk_score += 10
            elif pressure_ratio < 0.3:
                risk_score += 20
            elif pressure_ratio < 0.5:
                risk_score += 10

            return min(100, risk_score)

        except Exception as e:
            print(f'计算成交量风险失败: {e}')
            return 50

    def _prepare_volume_data(self, symbol: str) -> Dict:
        """准备成交量分析数据"""
        try:
            volume_data = {}
            if len(self.volume_buffers[symbol]) >= 5:
                volume_list = list(self.volume_buffers[symbol])

                # 计算最近的买卖量
                recent_bid_volume = sum(
                    v.get('bid_volume', 0) for v in volume_list[-5:]
                )
                recent_ask_volume = sum(
                    v.get('ask_volume', 0) for v in volume_list[-5:]
                )

                # 计算历史平均成交量
                historical_volumes = []
                for v in volume_list[:-5]:  # 排除最近的5个数据点
                    total_volume = v.get('bid_volume', 0) + v.get(
                        'ask_volume', 0
                    )
                    if total_volume > 0:
                        historical_volumes.append(total_volume)

                current_volume = recent_bid_volume + recent_ask_volume
                avg_volume = (
                    np.mean(historical_volumes)
                    if historical_volumes
                    else current_volume
                )

                volume_data = {
                    'bid_volume': recent_bid_volume,
                    'ask_volume': recent_ask_volume,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'ratio': current_volume / avg_volume
                    if avg_volume > 0
                    else 1.0,
                }

            return volume_data

        except Exception as e:
            print(f'准备成交量数据时出错: {e}')
            return {}

    def start_monitoring(self):
        """启动监控"""
        print('正在启动市场监控...')

        # 初始化数据
        self._initialize_data()

        # 设置运行标志
        self.running.set()

        # 启动WebSocket线程
        ws_thread = threading.Thread(target=self._start_websocket)
        ws_thread.daemon = True
        ws_thread.start()
        # 启动消息处理线程
        process_thread = threading.Thread(target=self._process_messages)
        process_thread.daemon = True
        process_thread.start()
        # 启动分析线程
        analysis_thread = threading.Thread(target=self._analysis_loop)
        analysis_thread.daemon = True
        analysis_thread.start()

        # 启动关键价位更新线程
        update_thread = threading.Thread(target=self._periodic_update_levels)
        update_thread.daemon = True
        update_thread.start()
        print('监控系统已启动')

    def stop(self):
        """停止监控"""
        print('正在停止监控...')
        self.running.clear()
        if self.ws:
            self.ws.close()
        print('监控已停止')


def main():
    # 设置要监控的交易对
    symbols = ['DOGEUSDT']

    try:
        monitor = MarketMonitor(symbols)
        monitor.start_monitoring()

        print('\n按Ctrl+C停止监控')

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        monitor.stop()


if __name__ == '__main__':
    main()
