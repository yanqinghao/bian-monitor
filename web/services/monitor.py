import numpy as np
import websocket
import json
import threading
import time
import os
import queue
from itertools import chain
from datetime import datetime
from typing import Dict, List
from collections import deque
from services.scan import MarketScanner
from analysis.data_fetcher import DataFetcher
from analysis.crypto_analyzer import CryptoAnalyzer
from analysis.technical_analyzer import TechnicalAnalyzer
from services.notifier import TelegramNotifier

# from dotenv import load_dotenv

# load_dotenv()


class MarketMonitor:
    def __init__(self, symbols: List[str] = [], use_proxy: bool = False):
        # Base configuration
        self.base_url = 'https://api.binance.com/api/v3'
        self.ws_url = 'wss://stream.binance.com:443/stream?streams='
        self.proxies = (
            {'http': 'http://127.0.0.1:1088', 'https': 'http://127.0.0.1:1088'}
            if use_proxy
            else None
        )

        # Symbol management
        self.user_define_symbols = [s.lower() for s in symbols]
        self.symbols = self.user_define_symbols

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

        # Analysis components
        self.technical_analyzer = TechnicalAnalyzer()
        self.scanner = MarketScanner()

        # Thread management
        self.message_queue = queue.Queue()
        self.running = threading.Event()
        self.ws = None
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
            top_symbols = self.scanner.get_top_symbols(top_n=20)

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
                self.symbols = new_symbols

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

    def _prepare_volume_data(self, symbol: str) -> Dict:
        """改进成交量数据处理"""
        try:
            volume_data = {}
            if len(self.volume_buffers[symbol]) >= 5:
                volume_list = list(self.volume_buffers[symbol])

                # 计算近期成交量
                recent_bid_volume = sum(
                    v.get('bid_volume', 0) for v in volume_list[-5:]
                )
                recent_ask_volume = sum(
                    v.get('ask_volume', 0) for v in volume_list[-5:]
                )

                # 计算历史成交量（使用更长的历史数据）
                historical_volumes = []
                for v in volume_list[:-5]:
                    total_volume = v.get('bid_volume', 0) + v.get(
                        'ask_volume', 0
                    )
                    if total_volume > 0:
                        historical_volumes.append(total_volume)

                current_volume = recent_bid_volume + recent_ask_volume

                # 使用加权平均处理历史成交量
                if historical_volumes:
                    weights = np.linspace(0.5, 1.0, len(historical_volumes))
                    avg_volume = np.average(
                        historical_volumes, weights=weights
                    )
                else:
                    avg_volume = current_volume

                volume_data = {
                    'bid_volume': recent_bid_volume,
                    'ask_volume': recent_ask_volume,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'ratio': current_volume / avg_volume
                    if avg_volume > 0
                    else 1.0,
                    'pressure_ratio': recent_bid_volume / recent_ask_volume
                    if recent_ask_volume > 0
                    else 1.0,
                }

            return volume_data

        except Exception as e:
            print(f'准备成交量数据时出错: {e}')
            return {}

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

    def _handle_kline_data(self, data):
        """Handle incoming kline data"""
        try:
            symbol = data['s'].lower()
            kline = data['k']

            with self.data_lock:
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

                self.latest_data[symbol] = {
                    'price': float(kline['c']),
                    'volume': float(kline['v']),
                }

        except Exception as e:
            print(f'处理K线数据失败: {e}')
            import traceback

            print(traceback.format_exc())

    def _handle_depth_data(self, data, stream):
        """Handle incoming depth data"""
        try:
            symbol = stream.split('@')[0]
            bid_volume = sum(float(bid[1]) for bid in data['bids'][:5])
            ask_volume = sum(float(ask[1]) for ask in data['asks'][:5])

            with self.data_lock:
                self.volume_buffers[symbol].append(
                    {
                        'time': datetime.now(),
                        'bid_volume': bid_volume,
                        'ask_volume': ask_volume,
                    }
                )

        except Exception as e:
            print(f'处理深度数据失败: {e}')
            import traceback

            print(traceback.format_exc())

    def _process_messages(self):
        """Process WebSocket messages"""
        while self.running.is_set():
            try:
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
                time.sleep(0.1)

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

    def _analysis_loop(self):
        """改进后的分析循环，支持多时间周期"""
        while self.running.is_set():
            try:
                current_time = datetime.now()
                batch_signals = []

                for symbol in self.symbols:
                    with self.data_lock:
                        if symbol in self.latest_data:
                            current_price = self.latest_data[symbol]['price']

                            # 获取各个时间周期的K线数据
                            kline_data_4h = []
                            kline_data_1h = []
                            kline_data_15m = []

                            # 获取4小时数据
                            klines_4h = DataFetcher.get_kline_data(
                                symbol.upper(), '4h', 15
                            )
                            for _, row in klines_4h.iterrows():
                                kline_data_4h.append(
                                    self._format_kline_data(row)
                                )

                            # 获取1小时数据
                            klines_1h = DataFetcher.get_kline_data(
                                symbol.upper(), '1h', 15
                            )
                            for _, row in klines_1h.iterrows():
                                kline_data_1h.append(
                                    self._format_kline_data(row)
                                )

                            # 获取15分钟数据
                            klines_15m = DataFetcher.get_kline_data(
                                symbol.upper(), '15m', 15
                            )
                            for _, row in klines_15m.iterrows():
                                kline_data_15m.append(
                                    self._format_kline_data(row)
                                )

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

                            # 计算指标
                            indicators = (
                                self.technical_analyzer.calculate_indicators(
                                    kline_data_4h,
                                    kline_data_1h,
                                    kline_data_15m,
                                )
                            )

                            # 生成信号
                            signals = self.technical_analyzer.generate_trading_signals(
                                indicators=indicators,
                                price=current_price,
                                key_levels=self.key_levels.get(symbol, {}),
                                volume_data=volume_data,
                            )

                            # 处理信号
                            for signal in signals:
                                if signal['type'] in [
                                    'buy',
                                    'sell',
                                    'strong_buy',
                                    'strong_sell',
                                ]:
                                    batch_signals.append(
                                        {
                                            'symbol': symbol,
                                            'price': current_price,
                                            'signal_type': signal['type'],
                                            'score': signal['score'],
                                            'technical_score': signal[
                                                'technical_score'
                                            ],
                                            'trend_alignment': signal.get(
                                                'trend_alignment', '未知'
                                            ),
                                            'volume_data': volume_data,
                                            'risk_level': signal.get(
                                                'risk_level', 'medium'
                                            ),
                                            'reason': signal.get('reason', ''),
                                        }
                                    )

                            # Console输出
                            if signals:
                                self._output_signals(
                                    symbol,
                                    signals,
                                    current_time,
                                    current_price,
                                    volume_data,
                                )

                            # # 监控异常波动
                            # self._monitor_abnormal_movements(
                            #     symbol, indicators, volume_data
                            # )

                # if self.telegram:
                #     self.telegram.send_alert_message()

                # 发送批量信号
                if batch_signals and self.telegram:
                    self._send_batch_telegram_alerts(batch_signals)

                time.sleep(300)  # 5分钟检查一次

            except Exception as e:
                print(f'分析过程出错: {e}')
                time.sleep(0.1)

    def _send_batch_telegram_alerts(self, batch_signals: List[Dict]):
        """发送批量Telegram通知，支持多时间周期信息"""
        if not self.telegram:
            return

        for signal in batch_signals:
            if signal['signal_type'] in [
                'buy',
                'sell',
                'strong_buy',
                'strong_sell',
            ]:
                # 构建更详细的消息
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

                trend_alignment = signal.get('trend_alignment', '')

                message = self.telegram.format_signal_message(
                    symbol=signal['symbol'],
                    signal_type=signal['signal_type'],
                    current_price=signal['price'],
                    signal_score=signal['score'],
                    technical_scores=', '.join(scores_text),
                    trend_alignment=trend_alignment,
                    volume_data=signal['volume_data'],
                    risk_level=signal['risk_level'],
                    reason=signal['reason'],
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
            ('WebSocket', self._start_websocket),
            ('Message Processing', self._process_messages),
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
        if self.ws:
            self.ws.close()
        print('监控已停止')

    def _reconnect(self):
        """重新连接WebSocket"""
        if self.running.is_set():
            print('正在尝试重新连接...')
            time.sleep(5)  # 等待5秒后重连
            threading.Thread(target=self._start_websocket).start()
