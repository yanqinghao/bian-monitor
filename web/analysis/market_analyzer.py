import talib
import numpy as np
import pandas as pd
from enum import Enum
from typing import Dict, List, Tuple, Optional


class MarketCycle(Enum):
    BULL = '牛市'
    BEAR = '熊市'
    CONSOLIDATION = '震荡'
    BULL_BREAKOUT = '牛市突破'
    BEAR_BREAKDOWN = '熊市崩溃'


class EnhancedMarketAnalyzer:
    def __init__(self):
        self.cycle_ma_periods = [20, 60, 120]  # 用于判断市场周期的均线
        self.breakout_threshold = 0.02  # 突破阈值
        self.consolidation_threshold = 0.05  # 震荡区间阈值

    def analyze_market_state(
        self, daily_data: pd.DataFrame, current_price: float
    ) -> Dict:
        """
        综合分析市场状态，包括市场周期、关键位置和交易建议

        Args:
            daily_data: 日线数据，至少90天
            current_price: 当前价格

        Returns:
            包含市场状态分析的字典
        """
        try:
            # 计算关键指标
            ma_data = self._calculate_moving_averages(daily_data)
            cycle = self._determine_market_cycle(daily_data, ma_data)
            key_levels = self._identify_key_levels(daily_data, current_price)
            position_score = self._evaluate_price_position(
                current_price, key_levels, ma_data, cycle
            )

            # 生成详细分析
            analysis = {
                'market_cycle': cycle,
                'key_levels': key_levels,
                'position_score': position_score,
                'ma_trend': self._analyze_ma_trend(ma_data, current_price),
                'support_resistance': self._analyze_sr_levels(
                    current_price, key_levels
                ),
                'trend_strength': self._calculate_trend_strength(
                    daily_data, cycle
                ),
                'breakdown_breakout': self._detect_breakdown_breakout(
                    current_price, key_levels, cycle
                ),
            }

            # 添加交易建议
            analysis['trading_advice'] = self._generate_trading_advice(
                analysis
            )

            return analysis

        except Exception as e:
            print(f'市场状态分析失败: {e}')
            return {}

    def _calculate_moving_averages(self, df: pd.DataFrame) -> Dict[int, float]:
        """计算多个周期的移动平均线"""
        ma_dict = {}
        for period in self.cycle_ma_periods:
            ma_dict[period] = talib.SMA(df['Close'].values, timeperiod=period)[
                -1
            ]
        return ma_dict

    def _determine_market_cycle(
        self, df: pd.DataFrame, ma_data: Dict[int, float]
    ) -> MarketCycle:
        """
        判断当前市场周期

        规则:
        1. 多头排列（短期均线>中期均线>长期均线）且强势上涨 = 牛市
        2. 空头排列（短期均线<中期均线<长期均线）且持续下跌 = 熊市
        3. 均线交织且价格在一定范围内波动 = 震荡
        4. 突破前期高点且成交量放大 = 牛市突破
        5. 跌破关键支撑且成交量放大 = 熊市崩溃
        """
        current_price = df['Close'].iloc[-1]
        ma20, ma60, ma120 = [ma_data[p] for p in self.cycle_ma_periods]

        # 计算价格波动
        volatility = df['Close'].pct_change().std() * np.sqrt(252)
        price_range = (df['High'].max() - df['Low'].min()) / df['Low'].min()

        # 判断市场特征
        if (
            ma20 > ma60 > ma120
            and current_price > ma20
            and volatility < self.breakout_threshold
        ):
            # 检查是否是突破性牛市
            if (
                current_price
                > df['High'].rolling(window=60).max().shift(1).iloc[-1]
                and df['Volume'].iloc[-1]
                > df['Volume'].rolling(window=20).mean().iloc[-1] * 1.5
            ):
                return MarketCycle.BULL_BREAKOUT
            return MarketCycle.BULL

        elif (
            ma20 < ma60 < ma120
            and current_price < ma20
            and volatility < self.breakout_threshold
        ):
            # 检查是否是崩溃性熊市
            if (
                current_price
                < df['Low'].rolling(window=60).min().shift(1).iloc[-1]
                and df['Volume'].iloc[-1]
                > df['Volume'].rolling(window=20).mean().iloc[-1] * 1.5
            ):
                return MarketCycle.BEAR_BREAKDOWN
            return MarketCycle.BEAR

        elif price_range < self.consolidation_threshold:
            return MarketCycle.CONSOLIDATION

        # 默认返回震荡
        return MarketCycle.CONSOLIDATION

    def _identify_key_levels(
        self, df: pd.DataFrame, current_price: float
    ) -> Dict[str, List[float]]:
        """
        识别关键价格水平

        包括:
        1. 历史支撑位和阻力位
        2. 高成交量区域
        3. 突破/跌破后的反转位
        4. 黄金分割位
        """
        levels = {
            'support': [],
            'resistance': [],
            'volume_levels': [],
            'fibonacci_levels': [],
        }

        # 计算高成交量价格水平
        volume_profile = (
            df.groupby(pd.cut(df['Close'], bins=50))['Volume']
            .sum()
            .sort_values(ascending=False)
        )
        high_volume_prices = volume_profile.head(3).index.map(lambda x: x.mid)
        levels['volume_levels'] = sorted(high_volume_prices)

        # 计算斐波那契回调位
        high = df['High'].max()
        low = df['Low'].min()
        price_range = high - low
        levels['fibonacci_levels'] = [
            high,
            high - price_range * 0.236,
            high - price_range * 0.382,
            high - price_range * 0.5,
            high - price_range * 0.618,
            low,
        ]

        # 识别支撑和阻力
        for i in range(20, len(df)):
            window = df.iloc[i - 20 : i + 1]
            price = df['Close'].iloc[i]

            # 寻找局部最高点和最低点
            if price == window['High'].max():
                levels['resistance'].append(price)
            elif price == window['Low'].min():
                levels['support'].append(price)

        # 对每个类别的水平进行聚类和过滤
        for key in levels:
            if levels[key]:
                levels[key] = self._cluster_price_levels(
                    levels[key], current_price
                )

        return levels

    def _cluster_price_levels(
        self, prices: List[float], current_price: float
    ) -> List[float]:
        """
        对价格水平进行聚类，合并相近的水平
        """
        if not prices:
            return []

        clustered = []
        prices = sorted(prices)
        current_cluster = [prices[0]]

        for price in prices[1:]:
            if (
                abs(price - np.mean(current_cluster)) / current_price
                < self.breakout_threshold
            ):
                current_cluster.append(price)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [price]

        clustered.append(np.mean(current_cluster))
        return sorted(clustered)

    def _evaluate_price_position(
        self,
        current_price: float,
        key_levels: Dict[str, List[float]],
        ma_data: Dict[int, float],
        market_cycle: MarketCycle,
    ) -> float:
        """
        评估当前价格位置的得分(0-100)

        考虑因素:
        1. 距离最近支撑位/阻力位的距离
        2. 均线系统位置
        3. 市场周期
        4. 成交量支撑
        """
        score = 50  # 基础分

        # 分析支撑位
        if key_levels['support']:
            nearest_support = max(
                [s for s in key_levels['support'] if s < current_price],
                default=min(key_levels['support']),
            )
            support_distance = (
                current_price - nearest_support
            ) / current_price
            if support_distance < 0.01:  # 非常接近支撑位
                score += 20
            elif support_distance < 0.03:
                score += 10

        # 分析阻力位
        if key_levels['resistance']:
            nearest_resistance = min(
                [r for r in key_levels['resistance'] if r > current_price],
                default=max(key_levels['resistance']),
            )
            resistance_distance = (
                nearest_resistance - current_price
            ) / current_price
            if resistance_distance < 0.01:  # 非常接近阻力位
                score -= 20
            elif resistance_distance < 0.03:
                score -= 10

        # 考虑市场周期
        cycle_adjustments = {
            MarketCycle.BULL: 15,
            MarketCycle.BULL_BREAKOUT: 20,
            MarketCycle.BEAR: -15,
            MarketCycle.BEAR_BREAKDOWN: -20,
            MarketCycle.CONSOLIDATION: 0,
        }
        score += cycle_adjustments[market_cycle]

        # 均线位置分析
        ma20 = ma_data[20]
        if current_price > ma20:
            score += 10
        else:
            score -= 10

        return max(0, min(100, score))

    def _analyze_ma_trend(
        self, ma_data: Dict[int, float], current_price: float
    ) -> Dict:
        """分析均线趋势"""
        ma20, ma60, ma120 = [ma_data[p] for p in self.cycle_ma_periods]

        trend = {
            'alignment': 'neutral',
            'strength': 0,
            'price_position': 'neutral',
        }

        # 判断均线排列
        if ma20 > ma60 > ma120:
            trend['alignment'] = 'bullish'
            trend['strength'] = 2 if (ma20 - ma120) / ma120 > 0.05 else 1
        elif ma20 < ma60 < ma120:
            trend['alignment'] = 'bearish'
            trend['strength'] = 2 if (ma120 - ma20) / ma20 > 0.05 else 1

        # 判断价格相对均线位置
        if current_price > ma20:
            trend['price_position'] = 'above_ma20'
        elif current_price < ma20:
            trend['price_position'] = 'below_ma20'

        return trend

    def _analyze_sr_levels(
        self, current_price: float, key_levels: Dict[str, List[float]]
    ) -> Dict:
        """分析支撑位和阻力位"""
        analysis = {
            'nearest_support': None,
            'nearest_resistance': None,
            'support_strength': 0,
            'resistance_strength': 0,
            'position': 'neutral',
        }

        # 找到最近的支撑位和阻力位
        if key_levels['support']:
            supports = [s for s in key_levels['support'] if s < current_price]
            if supports:
                analysis['nearest_support'] = max(supports)
                # 计算支撑强度（基于成交量和价格水平重合度）
                support_points = sum(
                    1
                    for level in key_levels['volume_levels']
                    if abs(level - analysis['nearest_support']) / current_price
                    < 0.01
                )
                analysis['support_strength'] = support_points

        if key_levels['resistance']:
            resistances = [
                r for r in key_levels['resistance'] if r > current_price
            ]
            if resistances:
                analysis['nearest_resistance'] = min(resistances)
                # 计算阻力强度
                resistance_points = sum(
                    1
                    for level in key_levels['volume_levels']
                    if abs(level - analysis['nearest_resistance'])
                    / current_price
                    < 0.01
                )
                analysis['resistance_strength'] = resistance_points

        # 判断价格位置
        if analysis['nearest_support'] and analysis['nearest_resistance']:
            support_distance = (
                current_price - analysis['nearest_support']
            ) / current_price
            resistance_distance = (
                analysis['nearest_resistance'] - current_price
            ) / current_price

            if support_distance < 0.01:
                analysis['position'] = 'at_support'
            elif resistance_distance < 0.01:
                analysis['position'] = 'at_resistance'
            elif support_distance < resistance_distance:
                analysis['position'] = 'closer_to_support'
            else:
                analysis['position'] = 'closer_to_resistance'

        return analysis

    def _calculate_trend_strength(
        self, df: pd.DataFrame, market_cycle: MarketCycle
    ) -> float:
        """计算趋势强度（0-1）"""
        # 计算价格动量
        roc = talib.ROC(df['Close'].values, timeperiod=14)
        momentum = np.mean(roc[-5:])

        # 计算趋势一致性
        ma_trend = talib.SMA(df['Close'].values, timeperiod=20)
        ma_slope = (ma_trend[-1] - ma_trend[-5]) / ma_trend[-5]

        # 结合市场周期调整强度
        cycle_multipliers = {
            MarketCycle.BULL: 1.2,
            MarketCycle.BULL_BREAKOUT: 1.5,
            MarketCycle.BEAR: 0.8,
            MarketCycle.BEAR_BREAKDOWN: 0.5,
            MarketCycle.CONSOLIDATION: 1.0,
        }

        strength = abs(momentum * ma_slope) * cycle_multipliers[market_cycle]
        return min(1.0, max(0.0, strength))

    def _detect_breakdown_breakout(
        self,
        current_price: float,
        key_levels: Dict[str, List[float]],
        market_cycle: MarketCycle,
    ) -> Dict:
        """
        检测突破/跌破情况

        Returns:
            Dict: {
                'type': 'breakout'/'breakdown'/'none',
                'level': float,  # 突破/跌破的价格位
                'strength': float,  # 突破强度 0-1
                'confirmation': bool  # 是否确认
            }
        """
        result = {
            'type': 'none',
            'level': None,
            'strength': 0,
            'confirmation': False,
        }

        # 检查是否有突破或跌破
        if key_levels['resistance']:
            nearest_resistance = min(
                [r for r in key_levels['resistance'] if r < current_price],
                default=None,
            )
            if nearest_resistance:
                break_margin = (
                    current_price - nearest_resistance
                ) / nearest_resistance
                if break_margin > 0.01:  # 1%以上视为有效突破
                    result.update(
                        {
                            'type': 'breakout',
                            'level': nearest_resistance,
                            'strength': min(1.0, break_margin * 10),
                            'confirmation': break_margin > 0.02
                            and market_cycle
                            in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT],
                        }
                    )

        if key_levels['support']:
            nearest_support = max(
                [s for s in key_levels['support'] if s > current_price],
                default=None,
            )
            if nearest_support:
                break_margin = (
                    nearest_support - current_price
                ) / nearest_support
                if break_margin > 0.01:
                    result.update(
                        {
                            'type': 'breakdown',
                            'level': nearest_support,
                            'strength': min(1.0, break_margin * 10),
                            'confirmation': break_margin > 0.02
                            and market_cycle
                            in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN],
                        }
                    )

        return result

    def _generate_trading_advice(self, analysis: Dict) -> Dict:
        """
        基于综合分析生成交易建议

        Returns:
            Dict: {
                'action': str,  # 建议操作
                'entry_price': float,  # 建议入场价
                'stop_loss': float,  # 止损价
                'targets': List[float],  # 目标价位
                'confidence': float,  # 信心指数 0-1
                'risk_reward': float,  # 风险收益比
                'reasoning': List[str],  # 建议理由
                'risk_level': str  # 风险等级
            }
        """
        advice = {
            'action': 'hold',
            'entry_price': None,
            'stop_loss': None,
            'targets': [],
            'confidence': 0.5,
            'risk_reward': 0,
            'reasoning': [],
            'risk_level': 'medium',
        }

        market_cycle = analysis['market_cycle']
        position_score = analysis['position_score']
        sr_analysis = analysis['support_resistance']
        ma_trend = analysis['ma_trend']
        breakdown_breakout = analysis['breakdown_breakout']
        trend_strength = analysis['trend_strength']

        # 1. 强势做多信号
        if self._should_buy_strong(analysis):
            advice.update(self._generate_buy_advice(analysis, 'strong'))

        # 2. 一般做多信号
        elif self._should_buy_normal(analysis):
            advice.update(self._generate_buy_advice(analysis, 'normal'))

        # 3. 强势做空信号
        elif self._should_sell_strong(analysis):
            advice.update(self._generate_sell_advice(analysis, 'strong'))

        # 4. 一般做空信号
        elif self._should_sell_normal(analysis):
            advice.update(self._generate_sell_advice(analysis, 'normal'))

        # 5. 观望信号
        else:
            advice.update(self._generate_hold_advice(analysis))

        return advice

    def _should_buy_strong(self, analysis: Dict) -> bool:
        """判断是否出现强势做多信号"""
        return (
            analysis['market_cycle']
            in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]
            and analysis['position_score'] >= 70
            and analysis['ma_trend']['alignment'] == 'bullish'
            and analysis['trend_strength'] >= 0.7
            and (
                analysis['support_resistance']['position'] == 'at_support'
                or analysis['breakdown_breakout']['type'] == 'breakout'
                and analysis['breakdown_breakout']['confirmation']
            )
        )

    def _should_buy_normal(self, analysis: Dict) -> bool:
        """判断是否出现一般做多信号"""
        return (
            analysis['position_score'] >= 60
            and analysis['ma_trend']['price_position'] == 'above_ma20'
            and analysis['trend_strength'] >= 0.5
            and analysis['support_resistance']['position']
            in ['closer_to_support', 'at_support']
        )

    def _should_sell_strong(self, analysis: Dict) -> bool:
        """判断是否出现强势做空信号"""
        return (
            analysis['market_cycle']
            in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]
            and analysis['position_score'] <= 30
            and analysis['ma_trend']['alignment'] == 'bearish'
            and analysis['trend_strength'] >= 0.7
            and (
                analysis['support_resistance']['position'] == 'at_resistance'
                or analysis['breakdown_breakout']['type'] == 'breakdown'
                and analysis['breakdown_breakout']['confirmation']
            )
        )

    def _should_sell_normal(self, analysis: Dict) -> bool:
        """判断是否出现一般做空信号"""
        return (
            analysis['position_score'] <= 40
            and analysis['ma_trend']['price_position'] == 'below_ma20'
            and analysis['trend_strength'] >= 0.5
            and analysis['support_resistance']['position']
            in ['closer_to_resistance', 'at_resistance']
        )

    def _generate_buy_advice(self, analysis: Dict, strength: str) -> Dict:
        """生成做多建议"""
        current_price = analysis['key_levels']['current_price']
        sr_analysis = analysis['support_resistance']

        # 设置止损位
        stop_loss = sr_analysis['nearest_support'] * 0.98  # 支撑位下方2%

        # 设置目标位
        targets = []
        if sr_analysis['nearest_resistance']:
            targets.append(sr_analysis['nearest_resistance'])  # 第一目标
            if len(analysis['key_levels']['resistance']) > 1:
                targets.append(analysis['key_levels']['resistance'][1])  # 第二目标

        # 计算风险收益比
        risk = current_price - stop_loss
        reward = sum([t - current_price for t in targets]) / len(targets)
        risk_reward = reward / risk if risk > 0 else 0

        # 设置信心指数
        confidence = 0.8 if strength == 'strong' else 0.6

        # 生成建议理由
        reasons = []
        if strength == 'strong':
            reasons.extend(
                [
                    f"处于{analysis['market_cycle'].value}阶段",
                    '多项技术指标高度看多',
                    f"位置评分: {analysis['position_score']}",
                    f"趋势强度: {analysis['trend_strength']:.2f}",
                ]
            )
        else:
            reasons.extend(
                ['技术指标偏多', f"位置评分: {analysis['position_score']}", '处于支撑位附近']
            )

        return {
            'action': 'strong_buy' if strength == 'strong' else 'buy',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'targets': targets,
            'confidence': confidence,
            'risk_reward': risk_reward,
            'reasoning': reasons,
            'risk_level': 'medium' if strength == 'strong' else 'high',
        }

    def _generate_sell_advice(self, analysis: Dict, strength: str) -> Dict:
        """生成做空建议"""
        current_price = analysis['key_levels']['current_price']
        sr_analysis = analysis['support_resistance']

        # 设置止损位
        stop_loss = sr_analysis['nearest_resistance'] * 1.02  # 阻力位上方2%

        # 设置目标位
        targets = []
        if sr_analysis['nearest_support']:
            targets.append(sr_analysis['nearest_support'])  # 第一目标
            if len(analysis['key_levels']['support']) > 1:
                targets.append(analysis['key_levels']['support'][1])  # 第二目标

        # 计算风险收益比
        risk = stop_loss - current_price
        reward = sum([current_price - t for t in targets]) / len(targets)
        risk_reward = reward / risk if risk > 0 else 0

        # 设置信心指数
        confidence = 0.8 if strength == 'strong' else 0.6

        # 生成建议理由
        reasons = []
        if strength == 'strong':
            reasons.extend(
                [
                    f"处于{analysis['market_cycle'].value}阶段",
                    '多项技术指标高度看空',
                    f"位置评分: {analysis['position_score']}",
                    f"趋势强度: {analysis['trend_strength']:.2f}",
                ]
            )
        else:
            reasons.extend(
                ['技术指标偏空', f"位置评分: {analysis['position_score']}", '处于阻力位附近']
            )

        return {
            'action': 'strong_sell' if strength == 'strong' else 'sell',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'targets': targets,
            'confidence': confidence,
            'risk_reward': risk_reward,
            'reasoning': reasons,
            'risk_level': 'medium' if strength == 'strong' else 'high',
        }

    def _generate_hold_advice(self, analysis: Dict) -> Dict:
        """生成观望建议"""
        reasons = [
            f"当前处于{analysis['market_cycle'].value}阶段",
            '技术指标方向不明确',
            f"位置评分: {analysis['position_score']}",
            '建议等待更好的入场机会',
        ]

        return {
            'action': 'hold',
            'entry_price': None,
            'stop_loss': None,
            'targets': [],
            'confidence': 0.5,
            'risk_reward': 0,
            'reasoning': reasons,
            'risk_level': 'low',
        }
