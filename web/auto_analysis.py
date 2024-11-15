import pandas as pd
from datetime import datetime, timedelta
import requests
import warnings

warnings.filterwarnings('ignore')


class CryptoAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.timeframes = {
            '15m': {'days': 7, 'label': '15分钟'},
            '1h': {'days': 15, 'label': '1小时'},
            '4h': {'days': 30, 'label': '4小时'},
            '1d': {'days': 90, 'label': '日线'},
        }
        self.data = {}

    def get_kline_data(self, interval, days):
        """获取K线数据"""
        url = 'https://api.binance.com/api/v3/klines'
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int(
            (datetime.now() - timedelta(days=days)).timestamp() * 1000
        )

        params = {
            'symbol': self.symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
            'limit': 1000,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return self.process_kline_data(response.json())
        except Exception as e:
            raise Exception(f'获取{interval}数据失败: {str(e)}')

    def process_kline_data(self, data):
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
            'rsi': rsi,
        }

    def analyze_trend(self, df, indicators):
        """分析趋势"""
        current_price = df['Close'].iloc[-1]
        ma_status = self.analyze_ma_trend(indicators['ma'])
        macd_status = self.analyze_macd(indicators['macd'])
        kdj_status = self.analyze_kdj(indicators['kdj'])

        change_24h = (
            ((df['Close'].iloc[-1] / df['Close'].iloc[-96]) - 1) * 100
            if len(df) > 96
            else 0
        )

        trend_analysis = {
            'current_price': current_price,
            'change_24h': change_24h,
            'ma_trend': ma_status,
            'macd_status': macd_status,
            'kdj_status': kdj_status,
            'trend_strength': self.calculate_trend_strength(df),
        }

        return trend_analysis

    def analyze_ma_trend(self, mas):
        """分析均线趋势"""
        current_mas = {k: v.iloc[-1] for k, v in mas.items()}
        sorted_mas = sorted(
            current_mas.items(), key=lambda x: x[1], reverse=True
        )

        if sorted_mas[0][0] == 'MA5' and sorted_mas[-1][0] == 'MA60':
            return {'pattern': '多头排列', 'strength': '强势', 'bias': '看多'}
        elif sorted_mas[-1][0] == 'MA5' and sorted_mas[0][0] == 'MA60':
            return {'pattern': '空头排列', 'strength': '弱势', 'bias': '看空'}
        else:
            return {'pattern': '交叉整理', 'strength': '震荡', 'bias': '中性'}

    def analyze_macd(self, macd_data):
        """分析MACD"""
        macd, signal, hist = (
            macd_data['macd'],
            macd_data['signal'],
            macd_data['hist'],
        )

        # 判断金叉死叉
        if (
            macd.iloc[-1] > signal.iloc[-1]
            and macd.iloc[-2] <= signal.iloc[-2]
        ):
            cross = '金叉'
        elif (
            macd.iloc[-1] < signal.iloc[-1]
            and macd.iloc[-2] >= signal.iloc[-2]
        ):
            cross = '死叉'
        else:
            cross = '无'

        return {
            'cross': cross,
            'histogram': hist.iloc[-1],
            'trend': '多头' if hist.iloc[-1] > 0 else '空头',
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
            'status': '超买'
            if j.iloc[-1] > 80
            else '超卖'
            if j.iloc[-1] < 20
            else '中性',
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
            'volatility': volatility,
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
                return 0.5  # 0.5%
            elif price < 1000:
                return 2  # 0.2%
            elif price < 10000:
                return 50  # 0.5%
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
        lows = recent_data[recent_data['Low'] < recent_data['Low'].shift(1)][
            'Low'
        ]

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
            current = int(price / magnitude) * magnitude
            for _ in range(count):
                if current < price:
                    levels.append(current)
                current -= magnitude

            # 添加半整数位
            if magnitude >= 100:
                levels.extend([level + magnitude / 2 for level in levels])

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
        all_supports.extend(
            [level for level in high_vol_levels if level < current_price]
        )

        # 添加心理关口
        all_supports.extend(
            [level for level in psych_supports if level < current_price]
        )

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
        recent_highs = recent_data[
            recent_data['High'] > recent_data['High'].shift(1)
        ]['High']
        psych_resistances = get_psychological_levels(
            current_price * 1.1
        )  # 往上看得远一点

        all_resistances = []

        # 添加近期高点
        all_resistances.extend(recent_highs[recent_highs > current_price])

        # 添加成交量高点
        all_resistances.extend(
            [level for level in high_vol_levels if level > current_price]
        )

        # 添加心理关口
        all_resistances.extend(
            [level for level in psych_resistances if level > current_price]
        )

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
                next_resistance = current_price * (
                    1 + price_steps[len(resistances)]
                )
                if (
                    not resistances
                    or (next_resistance - resistances[-1]) > price_range
                ):
                    resistances.append(next_resistance)

        return {'supports': supports[:3], 'resistances': resistances[:3]}

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
            'volume_trend': '放量'
            if volume_trend > 1.2
            else '缩量'
            if volume_trend < 0.8
            else '平稳',
        }

    def calculate_volatility_metrics(self, df):
        """计算波动率相关指标"""
        # 在class CryptoAnalyzer下增加此函数
        returns = df['Close'].pct_change()
        atr = self.calculate_atr(df)

        return {
            'returns_volatility': returns.std() * 100,
            'atr': atr,
            'atr_percent': (atr / df['Close'].mean()) * 100,
        }

    def calculate_atr(self, df, period=14):
        """计算ATR"""
        # 在class CryptoAnalyzer下增加此函数
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()

        return atr

    def analyze_volume_pattern(self, df):
        """分析成交量模式"""
        # 在class CryptoAnalyzer下增加此函数
        volume_ma = df['Volume'].rolling(20).mean()
        recent_volume = df['Volume'].tail(5).mean()
        volume_ratio = recent_volume / volume_ma.iloc[-1]

        volume_trend = pd.Series(df['Volume']).diff()
        volume_acceleration = volume_trend.diff()

        return {
            'volume_ma_ratio': volume_ratio,
            'volume_trend': 'up' if volume_trend.iloc[-1] > 0 else 'down',
            'volume_acceleration': volume_acceleration.iloc[-1],
            'is_volume_expanding': volume_ratio > 1.2,
        }

    def analyze_trading_strategy(self, df, key_levels):
        """生成交易策略建议"""
        # current_price = df['Close'].iloc[-1]
        # indicators = self.calculate_indicators(df)
        trend_stage = self.analyze_trend_stage(df)

        def calculate_position_size():
            """优化后的仓位计算"""
            # 修改 analyze_trading_strategy 方法中的 calculate_position_size 函数

            volatility = self.calculate_volatility_metrics(self.data['4h'])
            vol_pattern = self.analyze_volume_pattern(self.data['4h'])

            # 基础仓位设置
            base_position = {
                'aggressive': {'max': 50, 'step': 20},
                'moderate': {'max': 40, 'step': 15},
                'conservative': {'max': 30, 'step': 10},
            }

            # 风险评分
            risk_score = 0

            # 波动率评分
            if volatility['returns_volatility'] < 3:
                risk_score += 3
            elif volatility['returns_volatility'] < 5:
                risk_score += 2
            else:
                risk_score += 1

            # 趋势强度评分
            if abs(trend_stage['momentum']) > 2:
                risk_score += 3
            elif abs(trend_stage['momentum']) > 1:
                risk_score += 2
            else:
                risk_score += 1

            # 成交量评分
            if vol_pattern['is_volume_expanding']:
                risk_score += 2
            else:
                risk_score += 1

            # 选择仓位策略
            if risk_score >= 7:
                position = base_position['aggressive'].copy()
            elif risk_score >= 5:
                position = base_position['moderate'].copy()
            else:
                position = base_position['conservative'].copy()

            # 动态调整
            signal_strength = get_signal_strength()
            if signal_strength < 0.5:
                position['max'] = int(position['max'] * 0.8)
                position['step'] = int(position['step'] * 0.8)

            return position

        def get_signal_strength():
            """优化后的信号强度计算"""
            # 修改 analyze_trading_strategy 方法中的 get_signal_strength 函数

            # 获取技术指标数据
            indicators = self.calculate_indicators(self.data['4h'])
            vol_metrics = self.analyze_volume_pattern(self.data['4h'])
            volatility = self.calculate_volatility_metrics(self.data['4h'])

            weights = {
                'trend': 0.3,
                'technical': 0.3,
                'volume': 0.2,
                'price': 0.2,
            }

            # 趋势得分
            trend_score = 0
            if trend_stage['momentum'] < 0:
                trend_score += 0.6
            if (
                vol_metrics['volume_ma_ratio'] > 1.2
                and trend_stage['momentum'] < 0
            ):
                trend_score += 0.4

            # 技术指标得分
            tech_score = 0
            if indicators['macd']['hist'].iloc[-1] < 0:
                tech_score += 0.3
            if indicators['kdj']['j'].iloc[-1] > 80:
                tech_score += 0.4
            if indicators['rsi'].iloc[-1] > 70:
                tech_score += 0.3

            # 成交量得分
            volume_score = 0
            if vol_metrics['volume_ma_ratio'] < 0.8:
                volume_score += 0.5
            if vol_metrics['volume_trend'] == 'up':
                volume_score += 0.5

            # 价格结构得分
            price_score = 0
            current_price = self.data['4h']['Close'].iloc[-1]
            if current_price > indicators['ma']['MA20'].iloc[-1]:
                price_score += 0.5
            if volatility['returns_volatility'] > 5:
                price_score += 0.5

            final_score = (
                trend_score * weights['trend']
                + tech_score * weights['technical']
                + volume_score * weights['volume']
                + price_score * weights['price']
            )

            return final_score

        def calculate_entry_points(side='short'):
            """优化后的入场点计算，包含多空双向"""
            # 修改 analyze_trading_strategy 方法中的 calculate_entry_points 函数

            current_price = self.data['4h']['Close'].iloc[-1]
            volatility = self.calculate_volatility_metrics(self.data['4h'])
            vol_pattern = self.analyze_volume_pattern(self.data['4h'])
            indicators = self.calculate_indicators(self.data['4h'])

            entries = []

            if side == 'short':
                # 阻力位做空
                for resistance in key_levels['resistances']:
                    strength = (
                        'strong'
                        if indicators['rsi'].iloc[-1] > 70
                        else 'medium'
                    )
                    confidence = (
                        'high'
                        if vol_pattern['is_volume_expanding']
                        else 'medium'
                    )

                    entry = {
                        'price': resistance,
                        'type': '阻力位做空',
                        'strength': strength,
                        'confidence': confidence,
                        'risk_ratio': 1.5 if strength == 'strong' else 1.2,
                    }
                    entries.append(entry)

                # 反弹做空点
                bounce_levels = [
                    current_price * (1 + volatility['atr_percent'] / 100),
                    current_price * (1 + volatility['atr_percent'] / 100 * 2),
                ]

                for level in bounce_levels:
                    if level < max(key_levels['resistances']):
                        entry = {
                            'price': level,
                            'type': '反弹做空',
                            'strength': 'medium',
                            'confidence': 'medium',
                            'risk_ratio': 1.2,
                        }
                        entries.append(entry)

            elif side == 'long':
                # 支撑位做多
                for support in key_levels['supports']:
                    strength = (
                        'strong'
                        if indicators['rsi'].iloc[-1] < 30
                        else 'medium'
                    )
                    confidence = (
                        'high'
                        if vol_pattern['is_volume_expanding']
                        else 'medium'
                    )

                    entry = {
                        'price': support,
                        'type': '支撑位做多',
                        'strength': strength,
                        'confidence': confidence,
                        'risk_ratio': 1.5 if strength == 'strong' else 1.2,
                    }
                    entries.append(entry)

                # 回调做多点
                pullback_levels = [
                    current_price * (1 - volatility['atr_percent'] / 100),
                    current_price * (1 - volatility['atr_percent'] / 100 * 2),
                ]

                for level in pullback_levels:
                    if level > min(key_levels['supports']):
                        entry = {
                            'price': level,
                            'type': '回调做多',
                            'strength': 'medium',
                            'confidence': 'medium',
                            'risk_ratio': 1.2,
                        }
                        entries.append(entry)

                # 均线支撑位做多
                ma_supports = []
                for period in [20, 50]:
                    ma_price = indicators['ma'][f'MA{period}'].iloc[-1]
                    if ma_price < current_price:
                        ma_supports.append(
                            {
                                'price': ma_price,
                                'type': f'MA{period}支撑做多',
                                'strength': 'medium',
                                'confidence': 'medium',
                                'risk_ratio': 1.2,
                            }
                        )
                entries.extend(ma_supports)
            else:
                # 突破做多机会
                for resistance in key_levels['resistances']:
                    if resistance > current_price:
                        entry = {
                            'price': resistance,
                            'type': '突破做多',
                            'strength': 'medium',
                            'confidence': 'waiting',
                            'risk_ratio': 1.2,
                            'condition': f'价格突破{resistance}并有效确认后',
                        }
                        entries.append(entry)

                # 回调做多机会
                for support in key_levels['supports']:
                    if support < current_price:
                        entry = {
                            'price': support,
                            'type': '回调做多',
                            'strength': 'medium',
                            'confidence': 'waiting',
                            'risk_ratio': 1.2,
                            'condition': f'价格回调到{support}获得支撑后',
                        }
                        entries.append(entry)

                # 震荡区间交易机会
                range_high = min(key_levels['resistances'])
                range_low = max(key_levels['supports'])
                current_atr = volatility['atr'].iloc[-1]  # 获取最新的ATR值
                if range_high - range_low > current_atr * 2:  # 确保区间足够大
                    entries.extend(
                        [
                            {
                                'price': range_low,
                                'type': '区间下沿做多',
                                'strength': 'medium',
                                'confidence': 'waiting',
                                'risk_ratio': 1.2,
                                'condition': f'价格在{range_low}获得支撑并出现反转信号',
                            },
                            {
                                'price': range_high,
                                'type': '区间上沿做空',
                                'strength': 'medium',
                                'confidence': 'waiting',
                                'risk_ratio': 1.2,
                                'condition': f'价格在{range_high}遇阻并出现反转信号',
                            },
                        ]
                    )

                # 均线交叉机会
                ma20 = indicators['ma']['MA20'].iloc[-1]
                ma60 = indicators['ma']['MA60'].iloc[-1]
                if abs(ma20 - ma60) / ma20 < 0.01:  # 均线即将交叉
                    entries.append(
                        {
                            'price': current_price,
                            'type': '均线交叉信号',
                            'strength': 'medium',
                            'confidence': 'waiting',
                            'risk_ratio': 1.2,
                            'condition': 'MA20和MA50发生金叉/死叉且成交量配合',
                        }
                    )

            # 根据趋势强度和价格位置筛选最佳入场点
            filtered_entries = []
            trend_strength = abs(trend_stage['momentum'])

            for entry in entries:
                # 计算价格与当前价的距离
                price_distance = (
                    abs(entry['price'] - current_price) / current_price
                )

                # 根据趋势强度调整可接受的价格距离
                max_distance = 0.05 if trend_strength > 2 else 0.03

                if price_distance <= max_distance:
                    # 计算综合得分
                    score = 0
                    score += 0.4 if entry['strength'] == 'strong' else 0.2
                    score += 0.4 if entry['confidence'] == 'high' else 0.2
                    score += 0.2 if entry['risk_ratio'] >= 1.5 else 0.1

                    entry['score'] = score
                    filtered_entries.append(entry)

            # 按得分和价格排序
            if side == 'long':
                filtered_entries.sort(key=lambda x: (-x['score'], x['price']))
            else:
                filtered_entries.sort(key=lambda x: (-x['score'], -x['price']))

            return filtered_entries[:3]  # 返回得分最高的3个入场点

        def calculate_stop_loss(side='short', entry_points=None):
            """优化后的止损计算，包含多空双向"""
            # 修改 analyze_trading_strategy 方法中的 calculate_stop_loss 函数

            volatility = self.calculate_volatility_metrics(self.data['4h'])
            indicators = self.calculate_indicators(self.data['4h'])

            stops = []

            if side == 'short':
                max_entry = max([e['price'] for e in entry_points])

                # 为每个入场点计算动态止损
                for entry in entry_points:
                    entry_price = entry['price']

                    # ATR止损
                    atr_stop = entry_price * (
                        1 + volatility['atr_percent'] / 100 * 2
                    )

                    # 波动率止损
                    vol_stop = entry_price * (
                        1 + volatility['returns_volatility'] / 100
                    )

                    # 技术指标止损 (如果RSI过低则收紧止损)
                    tech_stop = entry_price * (
                        1
                        + (0.015 if indicators['rsi'].iloc[-1] < 30 else 0.02)
                    )

                    # 取较小的止损位
                    stop_price = min(atr_stop, vol_stop, tech_stop)

                    stops.append(
                        {
                            'price': stop_price,
                            'type': f'动态止损 (入场价: {entry_price:.2f})',
                            'risk': f'{((stop_price - entry_price) / entry_price * 100):.1f}%',
                        }
                    )

                # 全局止损
                global_stop = max_entry * (
                    1 + max(volatility['returns_volatility'] / 100 * 1.5, 0.02)
                )
                stops.append(
                    {
                        'price': global_stop,
                        'type': '全局止损',
                        'risk': f'{((global_stop - max_entry) / max_entry * 100):.1f}%',
                    }
                )

            elif side == 'long':
                min_entry = min([e['price'] for e in entry_points])

                # 为每个入场点计算动态止损
                for entry in entry_points:
                    entry_price = entry['price']

                    # ATR止损
                    atr_stop = entry_price * (
                        1 - volatility['atr_percent'] / 100 * 2
                    )

                    # 波动率止损
                    vol_stop = entry_price * (
                        1 - volatility['returns_volatility'] / 100
                    )

                    # 技术指标止损 (如果RSI过高则收紧止损)
                    tech_stop = entry_price * (
                        1
                        - (0.015 if indicators['rsi'].iloc[-1] > 70 else 0.02)
                    )

                    # 取较大的止损位
                    stop_price = max(atr_stop, vol_stop, tech_stop)

                    # 确保止损不会低于最近支撑位
                    nearest_support = max(
                        [s for s in key_levels['supports'] if s < entry_price],
                        default=stop_price,
                    )
                    stop_price = max(
                        stop_price, nearest_support * 0.995
                    )  # 支撑位下方0.5%

                    stops.append(
                        {
                            'price': stop_price,
                            'type': f'动态止损 (入场价: {entry_price:.2f})',
                            'risk': f'{((entry_price - stop_price) / entry_price * 100):.1f}%',
                        }
                    )

                # 全局止损
                global_stop = min_entry * (
                    1 - max(volatility['returns_volatility'] / 100 * 1.5, 0.02)
                )

                # 确保全局止损不会太低
                lowest_support = min(key_levels['supports'])
                global_stop = max(
                    global_stop, lowest_support * 0.99
                )  # 最低支撑位下方1%

                stops.append(
                    {
                        'price': global_stop,
                        'type': '全局止损',
                        'risk': f'{((min_entry - global_stop) / min_entry * 100):.1f}%',
                    }
                )

            else:
                # 为每个潜在入场点计算预设止损
                stops = []
                for entry in entry_points:
                    if '做多' in entry['type']:
                        # 计算做多的预设止损
                        stop_price = entry['price'] * (
                            1 - volatility['atr_percent'] / 100 * 1.5
                        )
                        # 确保止损在最近支撑位下方
                        nearest_support = max(
                            [
                                s
                                for s in key_levels['supports']
                                if s < entry['price']
                            ],
                            default=stop_price,
                        )
                        current_stop = (
                            stop_price.iloc[-1]
                            if isinstance(stop_price, pd.Series)
                            else stop_price
                        )  # 取最新值
                        final_stop = max(current_stop, nearest_support * 0.995)

                        stops.append(
                            {
                                'entry_price': entry['price'],
                                'stop_price': final_stop,
                                'type': f"预设止损 ({entry['type']})",
                                'risk': f'{((entry["price"] - final_stop) / entry["price"] * 100):.1f}%',
                                'condition': entry['condition'],
                                'trigger_rules': [
                                    '确认突破后入场',
                                    '等待回抽确认支撑',
                                    '观察成交量配合',
                                    '关注技术指标背离',
                                ],
                            }
                        )

                    elif '做空' in entry['type']:
                        # 计算做空的预设止损
                        stop_price = entry['price'] * (
                            1 + volatility['atr_percent'] / 100 * 1.5
                        )
                        # 确保止损在最近阻力位上方
                        nearest_resistance = min(
                            [
                                r
                                for r in key_levels['resistances']
                                if r > entry['price']
                            ],
                            default=stop_price,
                        )
                        current_stop = (
                            stop_price.iloc[-1]
                            if isinstance(stop_price, pd.Series)
                            else stop_price
                        )  # 取最新值
                        final_stop = min(
                            current_stop, nearest_resistance * 1.005
                        )

                        stops.append(
                            {
                                'entry_price': entry['price'],
                                'stop_price': final_stop,
                                'type': f"预设止损 ({entry['type']})",
                                'risk': f'{((final_stop - entry["price"]) / entry["price"] * 100):.1f}%',
                                'condition': entry['condition'],
                                'trigger_rules': [
                                    '确认阻力后入场',
                                    '等待反弹确认阻力',
                                    '观察成交量配合',
                                    '关注技术指标背离',
                                ],
                            }
                        )

                # 添加观望期建议
                wait_suggestions = {
                    'waiting_conditions': [
                        '等待价格运行至关键支撑位或阻力位',
                        '等待均线系统形成明确方向',
                        'KDJ、RSI等指标出现超买超卖信号',
                        'MACD形成明确的金叉或死叉',
                        '成交量出现明显放大',
                    ],
                    'entry_confirmation': [
                        '价格突破需要放量确认',
                        '关键位置需要观察至少2个K线确认',
                        '建议使用小仓位试探性入场',
                        '入场后及时设置止损保护',
                    ],
                }

                return {
                    'potential_stops': stops,
                    'wait_suggestions': wait_suggestions,
                }

            # 添加移动止损建议
            if side == 'long':
                moving_stop = {
                    'initial': min([stop['price'] for stop in stops]),
                    'rules': [
                        '盈利1%时，将止损提升至成本价',
                        '盈利2%时，将止损提升至成本价上方0.5%',
                        '盈利3%时，将止损提升至成本价上方1%',
                        '后续每上涨1%，相应提升止损0.5%',
                    ],
                }
            else:
                moving_stop = {
                    'initial': max([stop['price'] for stop in stops]),
                    'rules': [
                        '盈利1%时，将止损下调至成本价',
                        '盈利2%时，将止损下调至成本价下方0.5%',
                        '盈利3%时，将止损下调至成本价下方1%',
                        '后续每下跌1%，相应下调止损0.5%',
                    ],
                }

            stops.append(
                {
                    'type': '移动止损建议',
                    'rules': moving_stop['rules'],
                    'initial_price': moving_stop['initial'],
                }
            )

            return {
                'fixed_stops': [
                    stop for stop in stops if stop['type'] != '移动止损建议'
                ],
                'moving_stop': moving_stop,
            }

        # 计算信号强度
        signal_strength = get_signal_strength()

        # 确定交易方向
        if signal_strength > 0.7:
            direction = 'short'
            bias = '强烈看空'
        elif signal_strength > 0.5:
            direction = 'short'
            bias = '偏空'
        elif signal_strength < 0.3:
            direction = 'wait'  # 改为观望
            bias = '信号较弱,建议观望'
        else:
            direction = 'wait'
            bias = '震荡调整'

        # 获取仓位建议
        position = calculate_position_size()
        # 先计算入场点
        entry_points = calculate_entry_points(side=direction)
        # 再基于入场点计算止损
        stops = calculate_stop_loss(side=direction, entry_points=entry_points)

        if direction == 'wait':
            # 获取潜在入场点
            potential_entries = calculate_entry_points('wait')
            # 获取潜在止损点
            potential_stops = calculate_stop_loss('wait', potential_entries)

            # 转换格式以适配现有数据结构
            entry_points = [
                {
                    'price': entry['price'],
                    'type': f"潜在{entry['type']} ({entry['condition']})",  # 合并condition到type中
                    'strength': entry['strength'],
                }
                for entry in potential_entries
            ]

            stops = [
                {
                    'price': stop['stop_price'],  # 使用预设的止损价格
                    'type': stop['type'],
                    'risk': stop['risk'],
                }
                for stop in potential_stops.get('potential_stops', [])
            ]

            # 构建符合原有格式的策略数据
            strategy = {
                'bias': '建议观望',
                'direction': direction,
                'signal_strength': f'{signal_strength:.2%}',
                'position': {'max': 0, 'step': 0},  # 观望时建议仓位为0
                'entry_points': entry_points,
                'stops': stops,
            }
        else:
            # 策略整合
            strategy = {
                'bias': bias,
                'direction': direction,
                'signal_strength': f'{signal_strength:.2%}',
                'position': position,
                'entry_points': entry_points,
                'stops': stops,
                'key_levels': key_levels,
            }

        return strategy

    def generate_strategy_report(self, strategy):
        """生成策略报告"""
        report = []

        report.extend(
            [
                '\n## 三、交易策略建议',
                f"### 市场倾向: {strategy['bias']}",
                f"- 信号强度: {strategy['signal_strength']}",
                f"- 建议方向: {'做多' if strategy['direction'] == 'long' else '做空' if strategy['direction'] == 'short' else '观望'}",
            ]
        )

        if strategy['direction'] != 'neutral':
            report.append('\n### 入场点位:')
            for i, entry in enumerate(strategy['entry_points'], 1):
                report.append(
                    f"{i}. {entry['price']:.4f} - {entry['type']} ({entry['strength']})"
                )

            report.extend(
                [
                    '\n### 仓位管理:',
                    f"- 建议最大仓位: {strategy['position']['max']}%",
                    '- 分批建仓:',
                    f"  * 首仓: {strategy['position']['step']}%",
                    f"  * 次仓: {strategy['position']['step']}%",
                    f"  * 末仓: {strategy['position']['max'] - 2*strategy['position']['step']}%",
                ]
            )

            report.append('\n### 止损方案:')
            for stop in strategy['stops']:
                report.append(
                    f"- {stop['type']}: {stop['price']:.4f} (风险: {stop['risk']})"
                )

        report.extend(
            [
                '\n### 策略要点:',
                f"1. {'逢低做多' if strategy['direction'] == 'long' else '高位做空' if strategy['direction'] == 'short' else '等待机会'}",
                '2. 严格执行止损',
                '3. 分批建仓',
                '4. 获利及时止盈',
            ]
        )

        return '\n'.join(report)

    def calculate_24h_change(self, df):
        """改进后的24小时涨跌幅计算"""
        # try:
        # 获取24小时前的价格
        price_24h_ago = None
        for i in range(len(df) - 1, -1, -1):
            if df.index[i] <= df.index[-1] - pd.Timedelta(hours=24):
                price_24h_ago = df['Close'][i]
                break

        if price_24h_ago is None:
            return 0

        current_price = df['Close'].iloc[-1]
        change_24h = ((current_price / price_24h_ago) - 1) * 100
        return change_24h

        # except Exception:
        #     return 0

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
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbol_name = (
            self.symbol[:-4] if self.symbol.endswith('USDT') else self.symbol
        )
        current_price = self.data['4h']['Close'].iloc[-1]

        report = [
            f'# {symbol_name}/USDT 技术分析报告',
            f'**报告时间**: {current_time}',
            f'**当前价格**: {current_price:.4f} USDT',
            f'**24h涨跌幅**: {change_24h:+.2f}%',
            '\n## 一、趋势分析',
            '### 趋势阶段分析',
        ]

        # 趋势阶段分析
        trend_stage = self.analyze_trend_stage(self.data['4h'])
        report.extend(
            [
                f"- 当前阶段: {trend_stage['stage']}",
                f"- 阶段特征: {trend_stage['description']}",
                f"- 成交量: {trend_stage['volume_trend']}",
                f"- 动能强度: {trend_stage['momentum']:.2f}%",
                f"- 波动幅度: {trend_stage['volatility']:.2f}%",
            ]
        )

        # 多周期分析
        report.append('\n### 多周期技术指标')
        for interval, df in self.data.items():
            indicators = self.calculate_indicators(df)
            analysis = self.analyze_trend(df, indicators)

            report.extend(
                [
                    f"\n#### {self.timeframes[interval]['label']}周期",
                    f"- 均线系统: {analysis['ma_trend']['pattern']}",
                    f"- MACD指标: {analysis['macd_status']['cross']}，趋势{analysis['macd_status']['trend']}",
                    f"- KDJ状态: {analysis['kdj_status']['status']}，J值{analysis['kdj_status']['j']:.2f}",
                ]
            )

        # 关键价位分析
        report.extend(['\n## 二、关键价位分析', '### 阻力位'])

        for i, resistance in enumerate(key_levels['resistances'], 1):
            diff = (resistance - current_price) / current_price * 100
            report.append(f'{i}. {resistance:.2f} (距今: +{diff:.2f}%)')

        report.append('\n### 支撑位')
        for i, support in enumerate(key_levels['supports'], 1):
            diff = (current_price - support) / support * 100
            report.append(f'{i}. {support:.2f} (距今: -{diff:.2f}%)')

        # 交易策略建议
        report.extend(
            [
                '\n## 三、交易策略建议',
                f"### 市场倾向: {strategy['bias']}",
                f"- 信号强度: {strategy['signal_strength']}",
                f"- 建议方向: {'做多' if strategy['direction'] == 'long' else '做空' if strategy['direction'] == 'short' else '观望'}",
            ]
        )

        if strategy['direction'] != 'neutral':
            report.append('\n### 入场点位:')
            for i, entry in enumerate(strategy['entry_points'], 1):
                report.append(
                    f"{i}. {entry['price']:.4f} - {entry['type']} ({entry['strength']})"
                )

            report.extend(
                [
                    '\n### 仓位管理:',
                    f"- 建议最大仓位: {strategy['position']['max']}%",
                    '- 分批建仓:',
                    f"  * 首仓: {strategy['position']['step']}%",
                    f"  * 次仓: {strategy['position']['step']}%",
                    f"  * 末仓: {strategy['position']['max'] - 2*strategy['position']['step']}%",
                ]
            )

            report.append('\n### 止损方案:')
            for stop in strategy['stops']:
                report.append(
                    f"- {stop['type']}: {stop['price']:.4f} (风险: {stop['risk']})"
                )

        # 操作建议总结
        report.extend(
            [
                '\n### 操作建议要点:',
                f"1. {'逢低做多' if strategy['direction'] == 'long' else '高位做空' if strategy['direction'] == 'short' else '等待机会'}",
                '2. 严格执行止损',
                '3. 分批建仓',
                '4. 获利及时止盈',
            ]
        )

        # 风险提示
        report.extend(
            [
                '\n## 四、风险提示',
                f"1. 当前波动率为 {trend_stage['volatility']:.2f}%，"
                + ('建议降低仓位' if trend_stage['volatility'] > 5 else '波动风险适中'),
                '2. 大盘走势可能影响个币表现，注意关注大盘动向',
                '3. 建议严格执行止损策略，控制风险',
                '4. 不要追高或抄底，耐心等待好的进场点',
                '\n注意：以上分析仅供参考，不构成投资建议，请根据自身情况作出判断',
            ]
        )

        return '\n'.join(report)

        # except Exception as e:
        #     return f"生成报告出错: {str(e)}"

    def generate_json_data(self):
        """生成JSON格式的分析数据"""
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

        # 当前基础信息
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbol_name = (
            self.symbol[:-4] if self.symbol.endswith('USDT') else self.symbol
        )
        current_price = self.data['4h']['Close'].iloc[-1]

        # 趋势阶段分析
        trend_stage = self.analyze_trend_stage(self.data['4h'])

        # 多周期分析
        timeframe_analysis = {}
        for interval, df in self.data.items():
            indicators = self.calculate_indicators(df)
            analysis = self.analyze_trend(df, indicators)

            timeframe_analysis[interval] = {
                'period': self.timeframes[interval]['label'],
                'ma_trend': analysis['ma_trend'],
                'macd': analysis['macd_status'],
                'kdj': analysis['kdj_status'],
            }
        # 构建JSON结构
        json_data = {
            'basic_info': {
                'symbol': f'{symbol_name}/USDT',
                'report_time': current_time,
                'current_price': float(current_price),
                'change_24h': float(change_24h),
            },
            'trend_analysis': {
                'current_stage': {
                    'stage': trend_stage['stage'],
                    'description': trend_stage['description'],
                    'volume_trend': trend_stage['volume_trend'],
                    'momentum': float(trend_stage['momentum']),
                    'volatility': float(trend_stage['volatility']),
                },
                'timeframe_analysis': timeframe_analysis,
            },
            'key_levels': {
                'resistances': [float(r) for r in key_levels['resistances']],
                'supports': [float(s) for s in key_levels['supports']],
            },
            'trading_strategy': {
                'bias': strategy['bias'],
                'direction': strategy['direction'],
                'signal_strength': float(
                    strategy['signal_strength'].strip('%')
                )
                / 100,
                'position': strategy['position'],
                'entry_points': [
                    {
                        'price': float(entry['price']),
                        'type': entry['type'],
                        'strength': entry['strength'],
                    }
                    for entry in strategy['entry_points']
                ],
                'stops': [
                    {
                        'price': float(stop['price']),
                        'type': stop['type'],
                        'risk': stop['risk'],
                    }
                    for stop in strategy['stops']
                ],
            },
            'risk_warnings': [
                f"当前波动率为 {trend_stage['volatility']:.2f}%，"
                + ('建议降低仓位' if trend_stage['volatility'] > 5 else '波动风险适中'),
                '大盘走势可能影响个币表现，注意关注大盘动向',
                '建议严格执行止损策略，控制风险',
                '不要追高或抄底，耐心等待好的进场点',
            ],
        }

        return json_data

        # except Exception as e:
        #     return {'error': True, 'message': f'生成JSON数据出错: {str(e)}'}


def main():
    # try:
    analyzer = CryptoAnalyzer('SUIUSDT')
    report = analyzer.generate_json_data()
    print(report)
    # except Exception as e:
    #     print(f'程序运行错误: {str(e)}')


def run(symbol):
    try:
        analyzer = CryptoAnalyzer(symbol)
        json_data = analyzer.generate_json_data()
        return json_data
    except Exception as e:
        return {'error': True, 'message': f'运行分析出错: {str(e)}'}


if __name__ == '__main__':
    main()
