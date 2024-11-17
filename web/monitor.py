import pandas as pd
import numpy as np
import talib
import requests
import websocket
import json
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

class MarketMonitor:
    def __init__(self, symbols: List[str], use_proxy: bool = True):
        self.base_url = "https://api.binance.com/api/v3"
        self.ws_url = "wss://stream.binance.com:443/stream?streams="
        self.proxies = {
            'http': 'http://127.0.0.1:1088',
            'https': 'http://127.0.0.1:1088'
        } if use_proxy else None
        
        self.symbols = [s.lower() for s in symbols]
        self.kline_buffers = {symbol: deque(maxlen=100) for symbol in self.symbols}
        self.volume_buffers = {symbol: deque(maxlen=20) for symbol in self.symbols}
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

    def _initialize_data(self):
        """初始化数据"""
        for symbol in self.symbols:
            try:
                klines = self._get_klines(symbol.upper())
                if not klines.empty:
                    with self.data_lock:
                        self.key_levels[symbol] = self._calculate_key_levels(klines)
                        for _, row in klines.iterrows():
                            self.kline_buffers[symbol].append({
                                'open_time': row['open_time'],
                                'open': float(row['open']),
                                'high': float(row['high']),
                                'low': float(row['low']),
                                'close': float(row['close']),
                                'volume': float(row['volume'])
                            })
            except Exception as e:
                print(f"初始化{symbol}数据失败: {e}")


    def _start_websocket(self):
        """启动WebSocket连接"""
        def on_message(ws, message):
            if self.running.is_set():
                self.message_queue.put(message)

        def on_error(ws, error):
            print(f"WebSocket错误: {error}")
            self._reconnect()

        def on_close(ws, close_status_code, close_msg):
            print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
            self._reconnect()

        def on_open(ws):
            print("WebSocket连接已建立")

        # 准备订阅的streams
        streams = []
        for symbol in self.symbols:
            streams.extend([
                f"{symbol}@kline_5m",
                f"{symbol}@depth5@1000ms"  # 改为1秒更新一次
            ])
        
        ws_url = f"{self.ws_url}{'/'.join(streams)}"
        
        while self.running.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                
                self.ws.run_forever()
            except Exception as e:
                print(f"WebSocket连接异常: {e}")
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
                print(f"处理消息出错: {e}")
                time.sleep(0.1)  # 添加小延迟

    def _get_klines(self, symbol: str, interval: str = '1m', limit: int = 100) -> pd.DataFrame:
        """获取K线数据"""
        try:
            endpoint = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(
                endpoint,
                params=params,
                proxies=self.proxies,
                timeout=10
            )
            response.raise_for_status()
            
            # 转换数据为DataFrame
            df = pd.DataFrame(response.json(), columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades_count', 
                'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
            ])
            
            # 转换数据类型
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # 转换时间戳
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            return df
            
        except Exception as e:
            print(f"获取{symbol} K线数据失败: {e}")
            return pd.DataFrame()

    def _calculate_key_levels(self, df: pd.DataFrame) -> Dict:
        """计算关键价位"""
        try:
            if df.empty:
                return {}
                
            # 转换数据格式
            highs = df['high'].values
            lows = df['low'].values
            close = df['close'].values
            
            # SAR 指标
            sar = talib.SAR(highs, lows)
            
            # 布林带
            upper, middle, lower = talib.BBANDS(close, timeperiod=20)
            
            # 关键均线
            ma5 = talib.MA(close, timeperiod=5)
            ma10 = talib.MA(close, timeperiod=10)
            ma20 = talib.MA(close, timeperiod=20)
            ma60 = talib.MA(close, timeperiod=60)
            
            latest_close = close[-1]
            
            # 计算支点
            pivot = (highs[-1] + lows[-1] + close[-1]) / 3
            r1 = 2 * pivot - lows[-1]  # 阻力位1
            r2 = pivot + (highs[-1] - lows[-1])  # 阻力位2
            r3 = highs[-1] + 2 * (pivot - lows[-1])  # 阻力位3
            s1 = 2 * pivot - highs[-1]  # 支撑位1
            s2 = pivot - (highs[-1] - lows[-1])  # 支撑位2
            s3 = lows[-1] - 2 * (highs[-1] - pivot)  # 支撑位3
            
            # 收集所有可能的支撑位
            support_candidates = [
                s1, s2, s3,
                lower[-1],
                ma20[-1],
                ma60[-1],
                min(sar[-5:])  # 最近的SAR支撑
            ]
            
            # 收集所有可能的阻力位
            resistance_candidates = [
                r1, r2, r3,
                upper[-1],
                max(sar[-5:])  # 最近的SAR阻力
            ]
            
            # 过滤和聚类支撑位
            support_levels = []
            for level in sorted(support_candidates):
                if level < latest_close and (not support_levels or abs(level - support_levels[-1]) / latest_close > 0.002):
                    support_levels.append(level)
            
            # 过滤和聚类阻力位
            resistance_levels = []
            for level in sorted(resistance_candidates):
                if level > latest_close and (not resistance_levels or abs(level - resistance_levels[-1]) / latest_close > 0.002):
                    resistance_levels.append(level)
            
            return {
                'support_levels': support_levels[-5:],  # 取最近的5个支撑位
                'resistance_levels': resistance_levels[:5],  # 取最近的5个阻力位
                'current_price': latest_close,
                'ma5': ma5[-1],
                'ma10': ma10[-1],
                'ma20': ma20[-1],
                'ma60': ma60[-1],
                'bb_upper': upper[-1],
                'bb_lower': lower[-1],
                'bb_middle': middle[-1],
                'pivot': pivot,
                'update_time': datetime.now()
            }
            
        except Exception as e:
            print(f"计算关键价位失败: {e}")
            return {}
    
    def _periodic_update_levels(self):
        """定期更新关键价位"""
        while self.running.is_set():
            try:
                for symbol in self.symbols:
                    # 获取更长时间的K线数据用于计算关键价位
                    klines = self._get_klines(symbol.upper(), interval='1h', limit=500)
                    if not klines.empty:
                        with self.data_lock:
                            self.key_levels[symbol] = self._calculate_key_levels(klines)
                            print(f"已更新 {symbol} 的关键价位")
                
                # 一小时更新一次
                time.sleep(3600)
                
            except Exception as e:
                print(f"更新关键价位失败: {e}")
                time.sleep(60)  # 出错后等待1分钟再试

    def _handle_kline_data(self, data):
        """处理K线数据"""
        try:
            symbol = data['s'].lower()
            kline = data['k']
            
            # 使用锁保护数据更新
            with self.data_lock:
                # 更新K线缓存
                self.kline_buffers[symbol].append({
                    'open_time': datetime.fromtimestamp(int(kline['t']) / 1000),
                    'open': float(kline['o']),
                    'high': float(kline['h']),
                    'low': float(kline['l']),
                    'close': float(kline['c']),
                    'volume': float(kline['v'])
                })
                
                # 更新最新数据
                self.latest_data[symbol] = {
                    'price': float(kline['c']),
                    'volume': float(kline['v'])
                }
                
        except Exception as e:
            print(f"处理K线数据失败: {e}")

    def _handle_depth_data(self, data, symbol):
        """处理深度数据"""
        try:
            
            # 计算买卖压力
            bid_volume = sum(float(bid[1]) for bid in data['bids'][:5])
            ask_volume = sum(float(ask[1]) for ask in data['asks'][:5])
            
            # 使用锁保护数据更新
            with self.data_lock:
                # 更新量能缓存
                self.volume_buffers[symbol.split("@")[0]].append({
                    'time': datetime.now(),
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume
                })
                
        except Exception as e:
            print(f"处理深度数据失败: {e}")

    def _generate_signals(self, symbol: str, price: float, volume_ratio: float, 
                         volume_surge: bool, current_time: datetime):
        """生成交易信号"""
        try:
            # 检查最后提醒时间
            if symbol in self.last_alert_time:
                if (current_time - self.last_alert_time[symbol]).total_seconds() < 60:
                    return
            
            signals = []
            key_levels = self.key_levels.get(symbol, {})
            if not key_levels:
                return
            
            # 生成信号逻辑...
            support_levels = key_levels.get('support_levels', [])
            resistance_levels = key_levels.get('resistance_levels', [])
            
            # 支撑位信号
            for support in support_levels:
                if 0.995 <= price / support <= 1.005:
                    strength = 'strong' if volume_ratio > 1.2 and volume_surge else 'medium'
                    signals.append({
                        'type': 'buy',
                        'strength': strength,
                        'reason': f'价格接近支撑位 {support:.2f}, 买盘压力{"强" if strength == "strong" else "一般"}'
                    })
            
            # 阻力位信号
            for resistance in resistance_levels:
                if 0.995 <= price / resistance <= 1.005:
                    strength = 'strong' if volume_ratio < 0.8 and volume_surge else 'medium'
                    signals.append({
                        'type': 'sell',
                        'strength': strength,
                        'reason': f'价格接近阻力位 {resistance:.2f}, 卖盘压力{"强" if strength == "strong" else "一般"}'
                    })
            
            # 输出信号
            if signals:
                print(f"\n=== {symbol.upper()} 信号提醒 ===")
                print(f"时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"当前价格: {price:.2f}")
                print(f"买卖量比: {volume_ratio:.2f}")
                
                for signal in signals:
                    strength_stars = '★' * (2 if signal['strength'] == 'strong' else 1)
                    print(f"{signal['type'].upper()} {strength_stars}: {signal['reason']}")
                
                self.last_alert_time[symbol] = current_time
                
        except Exception as e:
            print(f"生成信号失败: {e}")

    def _reconnect(self):
        """重新连接WebSocket"""
        if self.running.is_set():
            print("正在尝试重新连接...")
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
                print(f"分析过程出错: {e}")
                time.sleep(0.1)

    def _analyze_symbol(self, symbol: str, current_time: datetime):
        """分析单个交易对"""
        try:
            current_price = self.latest_data[symbol]['price']
            
            # 获取最新volume数据
            if len(self.volume_buffers[symbol]) >= 5:
                volume_data = list(self.volume_buffers[symbol])
                recent_bid_volume = sum(v['bid_volume'] for v in volume_data[-5:])
                recent_ask_volume = sum(v['ask_volume'] for v in volume_data[-5:])
                
                # 计算量比
                volume_ratio = recent_bid_volume / recent_ask_volume if recent_ask_volume > 0 else 1
                
                # 计算量能突破
                avg_volume = np.mean([v['bid_volume'] + v['ask_volume'] for v in volume_data[:-5]])
                current_volume = recent_bid_volume + recent_ask_volume
                volume_surge = current_volume > avg_volume * 2
                
                # 生成信号
                self._generate_signals(symbol, current_price, volume_ratio, volume_surge, current_time)
                
        except Exception as e:
            print(f"分析{symbol}时出错: {e}")

    def start_monitoring(self):
        """启动监控"""
        print("正在启动市场监控...")
        
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
        print("监控系统已启动")

    def stop(self):
        """停止监控"""
        print("正在停止监控...")
        self.running.clear()
        if self.ws:
            self.ws.close()
        print("监控已停止")

def main():
    # 设置要监控的交易对
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']
    
    try:
        monitor = MarketMonitor(symbols)
        monitor.start_monitoring()
        
        print("\n按Ctrl+C停止监控")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        monitor.stop()

if __name__ == "__main__":
    main()