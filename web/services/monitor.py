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

    def _analyze_symbol(self, symbol: str, current_time: datetime):
        """改进单个交易对分析"""
        try:
            current_price = self.latest_data[symbol]['price']

            # 准备数据
            kline_data = list(self.kline_buffers[symbol])
            volume_data = self._prepare_volume_data(symbol)

            if not kline_data or not volume_data:
                return

            # 计算技术指标
            indicators = self.technical_analyzer.calculate_indicators(
                kline_data
            )

            # 生成交易信号
            signals = self.technical_analyzer.generate_trading_signals(
                indicators=indicators,
                price=current_price,
                key_levels=self.key_levels.get(symbol, {}),
                volume_data=volume_data,
            )

            # 输出信号
            if signals:
                self._output_signals(
                    symbol, signals, current_time, current_price, volume_data
                )

            # 记录异常波动
            self._monitor_abnormal_movements(symbol, indicators, volume_data)

        except Exception as e:
            print(f'分析{symbol}时出错: {e}')
            import traceback

            print(traceback.format_exc())

    def _monitor_abnormal_movements(
        self, symbol: str, indicators: Dict, volume_data: Dict
    ):
        """监控异常波动"""
        try:
            # 检查价格波动
            if 'volatility' in indicators:
                volatility = indicators['volatility']
                if volatility['atr_percent'] > 5:  # 5%以上的波动
                    print(
                        f"\n⚠️ {symbol} 价格波动异常: {volatility['atr_percent']:.2f}%"
                    )

            # 检查成交量异常
            if volume_data.get('ratio', 1) > 10:  # 10倍以上放量
                print(
                    f"\n⚠️ {symbol} 成交量异常: 当前量是均量的 {volume_data['ratio']:.2f} 倍"
                )

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
        """改进信号输出"""
        if not signals:
            return

        # 检查冷却时间
        if symbol in self.last_alert_time:
            # 根据信号类型调整冷却时间
            cooldown = 300  # 默认5分钟
            for signal in signals:
                if signal['type'] in ['strong_buy', 'strong_sell']:
                    cooldown = 180  # 强信号3分钟

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
            if 'ratio' in volume_data:
                volume_color = '🔴' if volume_data['ratio'] > 2 else '⚪️'
                print(f'成交量比率: {volume_color} {volume_data["ratio"]:.2f}')
            if 'pressure_ratio' in volume_data:
                pressure_color = (
                    '🔴'
                    if volume_data['pressure_ratio'] > 1.5
                    else ('🔵' if volume_data['pressure_ratio'] < 0.7 else '⚪️')
                )
                print(
                    f'买卖比: {pressure_color} {volume_data["pressure_ratio"]:.2f}'
                )

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
            print(f"技术得分: {signal.get('technical_score', 0):.1f}")
            print(f"支阻得分: {signal.get('sr_score', 0):.1f}")
            print(f"成交量得分: {signal.get('volume_score', 0):.1f}")

            # 添加风险等级显示
            risk_level_map = {
                'high': '⚠️ 高风险',
                'medium': '⚡️ 中等风险',
                'low': '✅ 低风险',
            }
            if 'risk_level' in signal:
                print(
                    f"风险等级: {risk_level_map.get(signal['risk_level'], '未知风险')}"
                )

            if 'reason' in signal:
                print(f"触发原因: {signal['reason']}")

        # 发送 Telegram 通知
        if self.telegram and any(
            signal['type'] in ['buy', 'sell', 'strong_buy', 'strong_sell']
            for signal in signals
        ):
            self._send_telegram_alerts(
                symbol, signals, current_price, volume_data
            )

        self.last_alert_time[symbol] = current_time
        print(f'{"="*50}\n')

    def _send_telegram_alerts(
        self,
        symbol: str,
        signals: List[Dict],
        current_price: float,
        volume_data: Dict,
    ):
        """改进Telegram通知"""
        for signal in signals:
            if signal['type'] in ['buy', 'sell', 'strong_buy', 'strong_sell']:
                # 构建更详细的消息
                risk_emoji = {'high': '⚠️', 'medium': '⚡️', 'low': '✅'}

                # 添加动量和趋势信息
                momentum = (
                    '强'
                    if signal['technical_score'] > 70
                    else ('中等' if signal['technical_score'] > 50 else '弱')
                )

                message = self.telegram.format_signal_message(
                    symbol=symbol,
                    signal_type=signal['type'],
                    current_price=current_price,
                    signal_score=signal['score'],
                    technical_score=signal.get('technical_score', 0),
                    volume_data=volume_data,
                    risk_level=f"{risk_emoji.get(signal.get('risk_level', 'high'), '⚠️')} {signal.get('risk_level', 'high')}",
                    momentum=momentum,
                    reason=signal.get('reason', ''),
                )
                self.telegram.send_message(message)

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
        """Main analysis loop"""
        while self.running.is_set():
            try:
                current_time = datetime.now()
                for symbol in self.symbols:
                    with self.data_lock:
                        if symbol in self.latest_data:
                            self._analyze_symbol(symbol, current_time)

                time.sleep(10)  # Analysis interval

            except Exception as e:
                print(f'分析过程出错: {e}')
                time.sleep(0.1)

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
