import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from scipy.stats import gaussian_kde
import warnings

warnings.filterwarnings('ignore')

class CryptoAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.timeframes = {
            '15m': {'days': 7, 'label': '15分钟'},
            '1h': {'days': 15, 'label': '1小时'},
            '4h': {'days': 30, 'label': '4小时'},
            '1d': {'days': 90, 'label': '日线'}
        }
        self.data = {}
        
    def get_kline_data(self, interval, days):
        """获取K线数据"""
        url = 'https://api.binance.com/api/v3/klines'
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        params = {
            'symbol': self.symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
            'limit': 1000
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return self.process_kline_data(response.json())
        except Exception as e:
            raise Exception(f'获取{interval}数据失败: {str(e)}')

    def process_kline_data(self, data):
        """处理K线数据"""
        df = pd.DataFrame(data, columns=[
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close time', 'Quote volume', 'Trades', 'Buy base', 'Buy quote', 'Ignore'
        ])
        
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
        df.set_index('Open time', inplace=True)
        
        return df

    def calculate_indicators(self, df):
        """计算技术指标"""
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        
        # KDJ
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        rsv = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        # MA均线
        ma_periods = [5, 10, 20, 60]
        mas = {}
        for period in ma_periods:
            mas[f'MA{period}'] = df['Close'].rolling(window=period).mean()
            
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        
        return {
            'macd': {'macd': macd, 'signal': signal, 'hist': hist},
            'kdj': {'k': k, 'd': d, 'j': j},
            'ma': mas,
            'rsi': rsi
        }

    def analyze_trend(self, df, indicators):
        """分析趋势"""
        current_price = df['Close'].iloc[-1]
        ma_status = self.analyze_ma_trend(indicators['ma'])
        macd_status = self.analyze_macd(indicators['macd'])
        kdj_status = self.analyze_kdj(indicators['kdj'])
        
        change_24h = ((df['Close'].iloc[-1] / df['Close'].iloc[-96]) - 1) * 100 if len(df) > 96 else 0
        
        trend_analysis = {
            'current_price': current_price,
            'change_24h': change_24h,
            'ma_trend': ma_status,
            'macd_status': macd_status,
            'kdj_status': kdj_status,
            'trend_strength': self.calculate_trend_strength(df)
        }
        
        return trend_analysis

    def analyze_ma_trend(self, mas):
        """分析均线趋势"""
        current_mas = {k: v.iloc[-1] for k, v in mas.items()}
        sorted_mas = sorted(current_mas.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_mas[0][0] == 'MA5' and sorted_mas[-1][0] == 'MA60':
            return {'pattern': '多头排列', 'strength': '强势', 'bias': '看多'}
        elif sorted_mas[-1][0] == 'MA5' and sorted_mas[0][0] == 'MA60':
            return {'pattern': '空头排列', 'strength': '弱势', 'bias': '看空'}
        else:
            return {'pattern': '交叉整理', 'strength': '震荡', 'bias': '中性'}

    def analyze_macd(self, macd_data):
        """分析MACD"""
        macd, signal, hist = macd_data['macd'], macd_data['signal'], macd_data['hist']
        
        # 判断金叉死叉
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            cross = '金叉'
        elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            cross = '死叉'
        else:
            cross = '无'
            
        return {
            'cross': cross,
            'histogram': hist.iloc[-1],
            'trend': '多头' if hist.iloc[-1] > 0 else '空头'
        }

    def analyze_kdj(self, kdj_data):
        """分析KDJ"""
        k, d, j = kdj_data['k'], kdj_data['d'], kdj_data['j']
        
        if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            cross = '金叉'
        elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
            cross = '死叉'
        else:
            cross = '无'
            
        return {
            'cross': cross,
            'k': k.iloc[-1],
            'd': d.iloc[-1],
            'j': j.iloc[-1],
            'status': '超买' if j.iloc[-1] > 80 else '超卖' if j.iloc[-1] < 20 else '中性'
        }

    def calculate_trend_strength(self, df):
        """计算趋势强度"""
        # 使用价格动量和波动率评估趋势强度
        momentum = df['Close'].pct_change(5).mean() * 100
        volatility = df['Close'].pct_change().std() * 100
        
        if abs(momentum) > 2 and volatility < 3:
            strength = '强势'
        elif abs(momentum) > 1:
            strength = '中等'
        else:
            strength = '弱势'
            
        return {
            'strength': strength,
            'momentum': momentum,
            'volatility': volatility
        }

    def find_key_levels(self, df):
        """改进后的关键价位计算
        
        1. 更合理的价格区间划分
        2. 考虑成交量峰值
        3. 结合技术指标
        4. 关注整数关口
        """
        current_price = df['Close'].iloc[-1]
        
        def get_price_range(price):
            """根据价格确定合理的价格区间"""
            if price < 1:
                return 0.01  # 1%
            elif price < 10:
                return 0.05  # 5%
            elif price < 100:
                return 0.5   # 0.5%
            elif price < 1000:
                return 2     # 0.2%
            elif price < 10000:
                return 50    # 0.5%
            else:
                return price * 0.005  # 0.5%
                
        price_range = get_price_range(current_price)
        
        # 计算支撑位
        supports = []
        
        # 1. 技术指标支撑位
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        ma50 = df['Close'].rolling(window=50).mean().iloc[-1]
        
        # 2. 近期低点
        recent_data = df.tail(100)  # 使用最近100根K线
        lows = recent_data[recent_data['Low'] < recent_data['Low'].shift(1)]['Low']
        
        # 3. 成交量加权价格
        volume_price = df.groupby('Low')['Volume'].sum()
        high_vol_levels = volume_price.nlargest(10).index
        
        # 4. 整数心理关口
        def get_psychological_levels(price, count=3):
            """获取心理整数关口"""
            levels = []
            # 获取价格数量级
            magnitude = 10 ** (len(str(int(price))) - 1)
            
            # 向下找最近的几个整数关口
            current = (int(price / magnitude) * magnitude)
            for _ in range(count):
                if current < price:
                    levels.append(current)
                current -= magnitude
                
            # 添加半整数位
            if magnitude >= 100:
                levels.extend([level + magnitude/2 for level in levels])
                
            return sorted(levels, reverse=True)
        
        psych_supports = get_psychological_levels(current_price)
        
        # 整合所有可能的支撑位
        all_supports = []
        
        # 添加技术指标支撑位
        if ma20 < current_price:
            all_supports.append(ma20)
        if ma50 < current_price:
            all_supports.append(ma50)
            
        # 添加近期低点
        all_supports.extend(lows[lows < current_price])
        
        # 添加成交量高点
        all_supports.extend([level for level in high_vol_levels if level < current_price])
        
        # 添加心理关口
        all_supports.extend([level for level in psych_supports if level < current_price])
        
        # 过滤和排序支撑位
        supports = []
        last_support = current_price
        
        # 对所有支撑位按价格降序排序
        all_supports = sorted(set(all_supports), reverse=True)
        
        # 筛选有意义的支撑位（间距要足够）
        for support in all_supports:
            if not supports or (last_support - support) > price_range:
                supports.append(support)
                last_support = support
            if len(supports) >= 3:
                break
                
        # 计算阻力位（同样的逻辑）
        resistances = []
        recent_highs = recent_data[recent_data['High'] > recent_data['High'].shift(1)]['High']
        psych_resistances = get_psychological_levels(current_price * 1.1)  # 往上看得远一点
        
        all_resistances = []
        
        # 添加近期高点
        all_resistances.extend(recent_highs[recent_highs > current_price])
        
        # 添加成交量高点
        all_resistances.extend([level for level in high_vol_levels if level > current_price])
        
        # 添加心理关口
        all_resistances.extend([level for level in psych_resistances if level > current_price])
        
        # 过滤和排序阻力位
        last_resistance = current_price
        all_resistances = sorted(set(all_resistances))
        
        for resistance in all_resistances:
            if not resistances or (resistance - last_resistance) > price_range:
                resistances.append(resistance)
                last_resistance = resistance
            if len(resistances) >= 3:
                break
        
        # 如果找不到足够的支撑位或阻力位，使用百分比
        if len(supports) < 3:
            price_steps = [0.05, 0.1, 0.15]  # 5%, 10%, 15%
            while len(supports) < 3:
                next_support = current_price * (1 - price_steps[len(supports)])
                if not supports or (supports[-1] - next_support) > price_range:
                    supports.append(next_support)
                    
        if len(resistances) < 3:
            price_steps = [0.05, 0.1, 0.15]  # 5%, 10%, 15%
            while len(resistances) < 3:
                next_resistance = current_price * (1 + price_steps[len(resistances)])
                if not resistances or (next_resistance - resistances[-1]) > price_range:
                    resistances.append(next_resistance)
        
        return {
            'supports': supports[:3],
            'resistances': resistances[:3]
        }

    def analyze_trend_stage(self, df):
        """改进后的趋势阶段分析"""
        # 计算趋势持续时间
        price_trend = df['Close'].diff().rolling(20).mean()
        current_trend = 'uptrend' if price_trend.iloc[-1] > 0 else 'downtrend'
        
        # 计算趋势强度
        momentum = df['Close'].pct_change(5).mean() * 100
        volatility = df['Close'].pct_change().std() * 100
        
        # 成交量分析
        volume_ma = df['Volume'].rolling(20).mean()
        recent_volume = df['Volume'].tail(5).mean()
        volume_trend = recent_volume / volume_ma.iloc[-1]
        
        # RSI位置
        rsi = self.calculate_indicators(df)['rsi'].iloc[-1]
        
        # 趋势阶段判断
        if current_trend == 'uptrend':
            if rsi > 70 and volume_trend < 0.8:
                stage = '上升趋势末期'
                desc = '出现超买信号,成交量萎缩'
            elif rsi > 60 and volume_trend > 1.2:
                stage = '上升趋势中期'
                desc = '动能强劲,成交量放大'
            else:
                stage = '上升趋势初期'
                desc = '突破盘整,开始上行'
        else:
            if rsi < 30 and volume_trend < 0.8:
                stage = '下降趋势末期'
                desc = '出现超卖信号,成交量萎缩'
            elif rsi < 40 and volume_trend > 1.2:
                stage = '下降趋势中期'
                desc = '跌势加剧,成交量放大'
            else:
                stage = '下降趋势初期'
                desc = '开始回落,需要观察'
                
        return {
            'stage': stage,
            'description': desc,
            'momentum': momentum,
            'volatility': volatility,
            'volume_trend': '放量' if volume_trend > 1.2 else '缩量' if volume_trend < 0.8 else '平稳'
        }

    def analyze_trading_strategy(self, df, key_levels):
        """生成交易策略建议"""
        current_price = df['Close'].iloc[-1]
        indicators = self.calculate_indicators(df)
        trend_stage = self.analyze_trend_stage(df)
        
        def calculate_position_size():
            """计算建议仓位大小"""
            # 基于波动率和趋势强度
            volatility = df['Close'].pct_change().std() * 100
            
            if volatility > 5:
                return {'max': 30, 'step': 10}  # 高波动低仓位
            elif volatility > 3:
                return {'max': 40, 'step': 15}  # 中等波动
            else:
                return {'max': 50, 'step': 20}  # 低波动可以较大仓位
        
        def get_signal_strength():
            """综合计算信号强度"""
            strength = 0
            
            # 1. 趋势判断
            if trend_stage['momentum'] > 0:
                strength += 1
            if trend_stage['volume_trend'] == '放量':
                strength += 1
                
            # 2. 技术指标判断
            # MACD
            if indicators['macd']['hist'].iloc[-1] > 0:
                strength += 1
            # KDJ
            if indicators['kdj']['j'].iloc[-1] > 50:
                strength += 1
            # RSI
            if indicators['rsi'].iloc[-1] > 50:
                strength += 1
            
            # 3. 均线系统
            ma_cross_up = False
            for period in [5, 10, 20]:
                if indicators['ma'][f'MA{period}'].iloc[-1] > indicators['ma'][f'MA{period}'].iloc[-2]:
                    ma_cross_up = True
                    strength += 0.5
                    
            return strength / 7  # 归一化到0-1之间
            
        def calculate_entry_points(side='long'):
            """计算入场点位"""
            supports = key_levels['supports']
            resistances = key_levels['resistances']
            entries = []
            
            if side == 'long':
                # 多头入场点
                # 1. 支撑位附近
                for support in supports:
                    entries.append({
                        'price': support,
                        'type': '支撑位买入',
                        'strength': '强' if support > indicators['ma']['MA20'].iloc[-1] else '中'
                    })
                    
                # 2. 回调买入点
                pullback_levels = [
                    current_price * 0.98,  # 2%回调
                    current_price * 0.95,  # 5%回调
                    current_price * 0.93   # 7%回调
                ]
                
                for level in pullback_levels:
                    if level > supports[-1]:  # 确保在最低支撑位之上
                        entries.append({
                            'price': level,
                            'type': '回调买入',
                            'strength': '中'
                        })
                        
            else:
                # 空头入场点
                # 1. 阻力位附近
                for resistance in resistances:
                    entries.append({
                        'price': resistance,
                        'type': '阻力位做空',
                        'strength': '强' if resistance < indicators['ma']['MA20'].iloc[-1] else '中'
                    })
                    
                # 2. 反弹做空点
                bounce_levels = [
                    current_price * 1.02,  # 2%反弹
                    current_price * 1.05,  # 5%反弹
                    current_price * 1.07   # 7%反弹
                ]
                
                for level in bounce_levels:
                    if level < resistances[-1]:  # 确保在最高阻力位之下
                        entries.append({
                            'price': level,
                            'type': '反弹做空',
                            'strength': '中'
                        })
                        
            return sorted(entries, key=lambda x: x['price'])
        
        def calculate_stop_loss(side='long'):
            """计算止损位"""
            volatility = df['Close'].pct_change().std() * 100
            atr = df['High'].iloc[-20:].max() - df['Low'].iloc[-20:].min()
            supports = key_levels['supports']
            resistances = key_levels['resistances']
            
            if side == 'long':
                # 多头止损
                stops = [
                    {
                        'price': supports[0] * 0.98,  # 支撑位下方2%
                        'type': '保守止损',
                        'risk': f'{((current_price - supports[0] * 0.98) / current_price * 100):.1f}%'
                    },
                    {
                        'price': min(supports) * 0.95,  # 最低支撑位下方5%
                        'type': '激进止损',
                        'risk': f'{((current_price - min(supports) * 0.95) / current_price * 100):.1f}%'
                    }
                ]
            else:
                # 空头止损
                stops = [
                    {
                        'price': resistances[0] * 1.02,  # 阻力位上方2%
                        'type': '保守止损',
                        'risk': f'{((resistances[0] * 1.02 - current_price) / current_price * 100):.1f}%'
                    },
                    {
                        'price': max(resistances) * 1.05,  # 最高阻力位上方5%
                        'type': '激进止损',
                        'risk': f'{((max(resistances) * 1.05 - current_price) / current_price * 100):.1f}%'
                    }
                ]
                
            return stops
        
        # 计算信号强度
        signal_strength = get_signal_strength()
        
        # 确定交易方向
        if signal_strength > 0.7:
            direction = 'long'
            bias = '强烈看多'
        elif signal_strength > 0.5:
            direction = 'long'
            bias = '偏多'
        elif signal_strength < 0.3:
            direction = 'short'
            bias = '强烈看空'
        elif signal_strength < 0.5:
            direction = 'short'
            bias = '偏空'
        else:
            direction = 'neutral'
            bias = '震荡'
            
        # 获取仓位建议
        position = calculate_position_size()
        
        # 生成交易建议
        strategy = {
            'bias': bias,
            'direction': direction,
            'signal_strength': f'{signal_strength:.2%}',
            'position': position,
            'entry_points': calculate_entry_points(direction),
            'stops': calculate_stop_loss(direction),
            'key_levels': key_levels
        }
        
        return strategy


    def generate_strategy_report(self, strategy):
        """生成策略报告"""
        report = []
        
        report.extend([
            "\n## 三、交易策略建议",
            f"### 市场倾向: {strategy['bias']}",
            f"- 信号强度: {strategy['signal_strength']}",
            f"- 建议方向: {'做多' if strategy['direction'] == 'long' else '做空' if strategy['direction'] == 'short' else '观望'}"
        ])
        
        if strategy['direction'] != 'neutral':
            report.append("\n### 入场点位:")
            for i, entry in enumerate(strategy['entry_points'], 1):
                report.append(f"{i}. {entry['price']:.4f} - {entry['type']} ({entry['strength']})")
                
            report.extend([
                "\n### 仓位管理:",
                f"- 建议最大仓位: {strategy['position']['max']}%",
                "- 分批建仓:",
                f"  * 首仓: {strategy['position']['step']}%",
                f"  * 次仓: {strategy['position']['step']}%",
                f"  * 末仓: {strategy['position']['max'] - 2*strategy['position']['step']}%"
            ])
            
            report.append("\n### 止损方案:")
            for stop in strategy['stops']:
                report.append(f"- {stop['type']}: {stop['price']:.4f} (风险: {stop['risk']})")
                
        report.extend([
            "\n### 策略要点:",
            f"1. {'逢低做多' if strategy['direction'] == 'long' else '高位做空' if strategy['direction'] == 'short' else '等待机会'}",
            "2. 严格执行止损",
            "3. 分批建仓",
            "4. 获利及时止盈"
        ])
        
        return "\n".join(report)

    def calculate_24h_change(self, df):
        """改进后的24小时涨跌幅计算"""
        try:
            # 获取24小时前的价格
            price_24h_ago = None
            for i in range(len(df)-1, -1, -1):
                if df.index[i] <= df.index[-1] - pd.Timedelta(hours=24):
                    price_24h_ago = df['Close'][i]
                    break
            
            if price_24h_ago is None:
                return 0
            
            current_price = df['Close'].iloc[-1]
            change_24h = ((current_price / price_24h_ago) - 1) * 100
            return change_24h
            
        except Exception:
            return 0

    def generate_report(self):
        """生成完整的分析报告"""
        # try:
        # 获取各时间周期数据
        for interval, info in self.timeframes.items():
            self.data[interval] = self.get_kline_data(interval, info['days'])
        
        # 使用4小时数据计算关键价位
        key_levels = self.find_key_levels(self.data['4h'])
        
        # 生成交易策略
        strategy = self.analyze_trading_strategy(self.data['4h'], key_levels)
        
        # 计算24小时涨跌幅
        change_24h = self.calculate_24h_change(self.data['1h'])
        
        # 生成报告
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbol_name = self.symbol[:-4] if self.symbol.endswith('USDT') else self.symbol
        current_price = self.data['4h']['Close'].iloc[-1]
        
        report = [
            f"# {symbol_name}/USDT 技术分析报告",
            f"**报告时间**: {current_time}",
            f"**当前价格**: {current_price:.4f} USDT",
            f"**24h涨跌幅**: {change_24h:+.2f}%",
            
            "\n## 一、趋势分析",
            "### 趋势阶段分析"
        ]
        
        # 趋势阶段分析
        trend_stage = self.analyze_trend_stage(self.data['4h'])
        report.extend([
            f"- 当前阶段: {trend_stage['stage']}",
            f"- 阶段特征: {trend_stage['description']}",
            f"- 成交量: {trend_stage['volume_trend']}",
            f"- 动能强度: {trend_stage['momentum']:.2f}%",
            f"- 波动幅度: {trend_stage['volatility']:.2f}%"
        ])
        
        # 多周期分析
        report.append("\n### 多周期技术指标")
        for interval, df in self.data.items():
            indicators = self.calculate_indicators(df)
            analysis = self.analyze_trend(df, indicators)
            
            report.extend([
                f"\n#### {self.timeframes[interval]['label']}周期",
                f"- 均线系统: {analysis['ma_trend']['pattern']}",
                f"- MACD指标: {analysis['macd_status']['cross']}，趋势{analysis['macd_status']['trend']}",
                f"- KDJ状态: {analysis['kdj_status']['status']}，J值{analysis['kdj_status']['j']:.2f}"
            ])
        
        # 关键价位分析
        report.extend([
            "\n## 二、关键价位分析",
            "### 阻力位"
        ])
        
        for i, resistance in enumerate(key_levels['resistances'], 1):
            diff = ((resistance - current_price) / current_price * 100)
            report.append(f"{i}. {resistance:.2f} (距今: +{diff:.2f}%)")
            
        report.append("\n### 支撑位")
        for i, support in enumerate(key_levels['supports'], 1):
            diff = ((current_price - support) / support * 100)
            report.append(f"{i}. {support:.2f} (距今: -{diff:.2f}%)")
        
        # 交易策略建议
        report.extend([
            "\n## 三、交易策略建议",
            f"### 市场倾向: {strategy['bias']}",
            f"- 信号强度: {strategy['signal_strength']}",
            f"- 建议方向: {'做多' if strategy['direction'] == 'long' else '做空' if strategy['direction'] == 'short' else '观望'}"
        ])
        
        if strategy['direction'] != 'neutral':
            report.append("\n### 入场点位:")
            for i, entry in enumerate(strategy['entry_points'], 1):
                report.append(f"{i}. {entry['price']:.4f} - {entry['type']} ({entry['strength']})")
                
            report.extend([
                "\n### 仓位管理:",
                f"- 建议最大仓位: {strategy['position']['max']}%",
                "- 分批建仓:",
                f"  * 首仓: {strategy['position']['step']}%",
                f"  * 次仓: {strategy['position']['step']}%",
                f"  * 末仓: {strategy['position']['max'] - 2*strategy['position']['step']}%"
            ])
            
            report.append("\n### 止损方案:")
            for stop in strategy['stops']:
                report.append(f"- {stop['type']}: {stop['price']:.4f} (风险: {stop['risk']})")
        
        # 操作建议总结
        report.extend([
            "\n### 操作建议要点:",
            f"1. {'逢低做多' if strategy['direction'] == 'long' else '高位做空' if strategy['direction'] == 'short' else '等待机会'}",
            "2. 严格执行止损",
            "3. 分批建仓",
            "4. 获利及时止盈"
        ])
        
        # 风险提示
        report.extend([
            "\n## 四、风险提示",
            f"1. 当前波动率为 {trend_stage['volatility']:.2f}%，" + 
            ("建议降低仓位" if trend_stage['volatility'] > 5 else "波动风险适中"),
            "2. 大盘走势可能影响个币表现，注意关注大盘动向",
            "3. 建议严格执行止损策略，控制风险",
            "4. 不要追高或抄底，耐心等待好的进场点",
            "\n注意：以上分析仅供参考，不构成投资建议，请根据自身情况作出判断"
        ])
        
        return "\n".join(report)
            
        # except Exception as e:
        #     return f"生成报告出错: {str(e)}"

def main():
    # try:
    analyzer = CryptoAnalyzer('DOGEUSDT')
    report = analyzer.generate_report()
    print(report)
    # except Exception as e:
    #     print(f"程序运行错误: {str(e)}")

def run(symbol):
    # try:
    analyzer = CryptoAnalyzer(symbol)
    report = analyzer.generate_report()
    return report

if __name__ == '__main__':
    main()
