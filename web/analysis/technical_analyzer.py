from typing import Dict, List
import numpy as np
import talib
from scipy.signal import find_peaks


class TechnicalAnalyzer:
    def __init__(self):
        # 设置各项指标的参数
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
        self.volume_ma_period = 20
        self.price_ma_periods = [5, 10, 20, 50]

    def calculate_indicators(self, kline_data: List[Dict]) -> Dict:
        """计算各项技术指标"""
        try:
            # 转换数据为numpy数组
            close_prices = np.array([k['close'] for k in kline_data])
            high_prices = np.array([k['high'] for k in kline_data])
            low_prices = np.array([k['low'] for k in kline_data])
            volumes = np.array([k['volume'] for k in kline_data])

            indicators = {
                'current_price': close_prices[-1]
                if len(close_prices) > 0
                else None
            }

            # 计算RSI
            if len(close_prices) > self.rsi_period:
                indicators['rsi'] = talib.RSI(
                    close_prices, timeperiod=self.rsi_period
                )[-1]

            # 计算MACD
            if len(close_prices) > self.macd_slow:
                macd, signal, hist = talib.MACD(
                    close_prices,
                    fastperiod=self.macd_fast,
                    slowperiod=self.macd_slow,
                    signalperiod=self.macd_signal,
                )
                indicators['macd'] = {
                    'macd': macd[-1],
                    'signal': signal[-1],
                    'hist': hist[-1],
                }

            # 计算布林带
            if len(close_prices) > self.bb_period:
                upper, middle, lower = talib.BBANDS(
                    close_prices,
                    timeperiod=self.bb_period,
                    nbdevup=self.bb_std,
                    nbdevdn=self.bb_std,
                )
                indicators['bollinger'] = {
                    'upper': upper[-1],
                    'middle': middle[-1],
                    'lower': lower[-1],
                }

            # 计算多周期均线
            indicators['ma'] = {}
            for period in self.price_ma_periods:
                if len(close_prices) > period:
                    indicators['ma'][period] = talib.SMA(
                        close_prices, timeperiod=period
                    )[-1]

            # 计算KDJ
            if len(close_prices) > 9:
                k, d = talib.STOCH(
                    high_prices,
                    low_prices,
                    close_prices,
                    fastk_period=9,
                    slowk_period=3,
                    slowk_matype=0,
                    slowd_period=3,
                    slowd_matype=0,
                )
                indicators['kdj'] = {
                    'k': k[-1],
                    'd': d[-1],
                    'j': 3 * k[-1] - 2 * d[-1],
                }

            # 计算成交量变化
            if len(volumes) > self.volume_ma_period:
                volume_ma = talib.SMA(
                    volumes, timeperiod=self.volume_ma_period
                )[-1]
                indicators['volume'] = {
                    'current': volumes[-1],
                    'ma': volume_ma,
                    'ratio': volumes[-1] / volume_ma if volume_ma > 0 else 1,
                }

            return indicators

        except Exception as e:
            print(f'计算指标时出错: {e}')
            return {}

    def analyze_price_pattern(self, kline_data: List[Dict]) -> Dict:
        """分析价格形态"""
        close_prices = np.array([k['close'] for k in kline_data])
        high_prices = np.array([k['high'] for k in kline_data])
        low_prices = np.array([k['low'] for k in kline_data])

        patterns = {}

        # 检测双底形态
        patterns['double_bottom'] = self._check_double_bottom(low_prices[-30:])

        # 检测双顶形态
        patterns['double_top'] = self._check_double_top(high_prices[-30:])

        # 检测趋势强度
        patterns['trend'] = self._analyze_trend_strength(close_prices[-20:])

        return patterns

    def generate_trading_signals(
        self,
        indicators: Dict,
        patterns: Dict,
        price: float,
        key_levels: Dict,
        volume_data: Dict,
    ) -> List[Dict]:
        """生成交易信号"""
        signals = []

        # 计算综合得分 (0-100)
        technical_score = self._calculate_technical_score(indicators)
        pattern_score = self._calculate_pattern_score(patterns)
        support_resistance_score = self._calculate_sr_score(price, key_levels)
        volume_score = self._calculate_volume_score(volume_data)

        # 综合得分加权计算
        total_score = (
            technical_score * 0.4
            + pattern_score * 0.2
            + support_resistance_score * 0.25
            + volume_score * 0.15
        )

        # 根据得分生成信号
        if total_score >= 75:
            signals.append(
                {
                    'type': 'strong_buy',
                    'score': total_score,
                    'reason': self._generate_signal_reason(
                        indicators, patterns, key_levels, volume_data, 'buy'
                    ),
                }
            )
        elif total_score >= 60:
            signals.append(
                {
                    'type': 'buy',
                    'score': total_score,
                    'reason': self._generate_signal_reason(
                        indicators, patterns, key_levels, volume_data, 'buy'
                    ),
                }
            )
        elif total_score <= 25:
            signals.append(
                {
                    'type': 'strong_sell',
                    'score': total_score,
                    'reason': self._generate_signal_reason(
                        indicators, patterns, key_levels, volume_data, 'sell'
                    ),
                }
            )
        elif total_score <= 40:
            signals.append(
                {
                    'type': 'sell',
                    'score': total_score,
                    'reason': self._generate_signal_reason(
                        indicators, patterns, key_levels, volume_data, 'sell'
                    ),
                }
            )

        return signals

    def _calculate_technical_score(self, indicators: Dict) -> float:
        """计算技术指标得分"""
        score = 50  # 基础分

        try:
            # RSI信号(0-20)
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                if rsi < 30:
                    score += 20 * (30 - rsi) / 30
                elif rsi > 70:
                    score -= 20 * (rsi - 70) / 30

            # MACD信号(0-20)
            if 'macd' in indicators:
                macd = indicators['macd']
                if macd['hist'] > 0 and macd['macd'] > macd['signal']:
                    score += 20
                elif macd['hist'] < 0 and macd['macd'] < macd['signal']:
                    score -= 20

            # 布林带信号(0-20)
            if 'bollinger' in indicators and all(
                k in indicators['bollinger']
                for k in ['upper', 'middle', 'lower']
            ):
                bb = indicators['bollinger']
                current_price = indicators.get(
                    'current_price', bb['middle']
                )  # 使用middle price作为默认值
                bb_position = (current_price - bb['lower']) / (
                    bb['upper'] - bb['lower']
                )
                if bb_position < 0.2:
                    score += 20 * (1 - bb_position / 0.2)
                elif bb_position > 0.8:
                    score -= 20 * (bb_position - 0.8) / 0.2

            # KDJ信号(0-20)
            if 'kdj' in indicators and all(
                k in indicators['kdj'] for k in ['k', 'd']
            ):
                kdj = indicators['kdj']
                if kdj['k'] < 20 and kdj['k'] > kdj['d']:
                    score += 20
                elif kdj['k'] > 80 and kdj['k'] < kdj['d']:
                    score -= 20

            # 均线多空(0-20)
            if 'ma' in indicators:
                ma = indicators['ma']
                ma_score = 0
                if all(k in ma for k in [5, 10, 20, 50]):
                    if ma[5] > ma[10] > ma[20] > ma[50]:
                        ma_score = 20
                    elif ma[5] < ma[10] < ma[20] < ma[50]:
                        ma_score = -20
                    score += ma_score

        except Exception as e:
            print(f'计算技术得分时出错: {e}')
            return 50  # 发生错误时返回中性分数

        return max(0, min(100, score))  # 确保分数在0-100之间

    def _calculate_pattern_score(self, patterns: Dict) -> float:
        """计算形态分析得分"""
        score = 50  # 基础分

        if patterns['double_bottom']:
            score += 25
        if patterns['double_top']:
            score -= 25

        trend = patterns['trend']
        if trend['strength'] == 'strong_up':
            score += 25
        elif trend['strength'] == 'weak_up':
            score += 15
        elif trend['strength'] == 'strong_down':
            score -= 25
        elif trend['strength'] == 'weak_down':
            score -= 15

        return max(0, min(100, score))

    def _calculate_sr_score(self, price: float, key_levels: Dict) -> float:
        """计算支撑压力位得分"""
        score = 50  # 基础分

        # 检查最近的支撑位
        supports = key_levels.get('supports', [])
        if supports:
            nearest_support = min(supports, key=lambda x: abs(x - price))
            if 0.99 <= price / nearest_support <= 1.01:
                score += 30
            elif 0.95 <= price / nearest_support <= 0.99:
                score += 20

        # 检查最近的阻力位
        resistances = key_levels.get('resistances', [])
        if resistances:
            nearest_resistance = min(resistances, key=lambda x: abs(x - price))
            if 0.99 <= price / nearest_resistance <= 1.01:
                score -= 30
            elif 1.01 <= price / nearest_resistance <= 1.05:
                score -= 20

        return max(0, min(100, score))

    def _calculate_volume_score(self, volume_data: Dict) -> float:
        """计算成交量分析得分"""
        try:
            score = 50  # 基础分

            # 检查volume_data是否为空
            if not volume_data:
                return score

            # 获取成交量比率，如果没有，则尝试计算
            volume_ratio = volume_data.get('ratio')
            if (
                volume_ratio is None
                and 'current_volume' in volume_data
                and 'avg_volume' in volume_data
            ):
                volume_ratio = (
                    volume_data['current_volume'] / volume_data['avg_volume']
                    if volume_data['avg_volume'] > 0
                    else 1
                )

            # 获取买卖压力比例
            bid_volume = volume_data.get('bid_volume', 0)
            ask_volume = volume_data.get('ask_volume', 0)
            bid_ask_ratio = bid_volume / ask_volume if ask_volume > 0 else 1

            # 评估成交量变化
            if volume_ratio is not None:
                if volume_ratio > 2:
                    score += 25
                elif volume_ratio > 1.5:
                    score += 15
                elif volume_ratio < 0.5:
                    score -= 25
                elif volume_ratio < 0.7:
                    score -= 15

            # 评估买卖压力
            if bid_volume > 0 or ask_volume > 0:  # 只有在有买卖量数据时才评估
                if bid_ask_ratio > 1.5:
                    score += 25
                elif bid_ask_ratio > 1.2:
                    score += 15
                elif bid_ask_ratio < 0.67:  # 1/1.5
                    score -= 25
                elif bid_ask_ratio < 0.83:  # 1/1.2
                    score -= 15

            return max(0, min(100, score))  # 确保得分在0-100之间

        except Exception as e:
            print(f'计算成交量得分时出错: {e}')
            return 50  # 发生错误时返回中性分数

    def _generate_signal_reason(
        self,
        indicators: Dict,
        patterns: Dict,
        key_levels: Dict,
        volume_data: Dict,
        signal_type: str,
    ) -> str:
        """生成信号原因说明"""
        reasons = []

        if signal_type == 'buy':
            if indicators['rsi'] < 30:
                reasons.append(f"RSI超卖({indicators['rsi']:.1f})")
            if indicators['macd']['hist'] > 0:
                reasons.append('MACD金叉')
            if patterns.get('double_bottom'):
                reasons.append('形成双底形态')
            if volume_data['ratio'] > 1.5:
                reasons.append(f"成交量放大{volume_data['ratio']:.1f}倍")

        else:  # sell
            if indicators['rsi'] > 70:
                reasons.append(f"RSI超买({indicators['rsi']:.1f})")
            if indicators['macd']['hist'] < 0:
                reasons.append('MACD死叉')
            if patterns.get('double_top'):
                reasons.append('形成双顶形态')
            if volume_data['ratio'] < 0.7:
                reasons.append(f"成交量萎缩{1/volume_data['ratio']:.1f}倍")

        return '，'.join(reasons)

    def _check_double_bottom(self, prices: np.ndarray) -> bool:
        """检测双底形态"""
        # 实现双底形态检测逻辑
        peaks, _ = find_peaks(-prices)  # 寻找低点
        if len(peaks) < 2:
            return False

        # 检查最后两个低点是否符合双底特征
        last_two_bottoms = prices[peaks[-2:]]
        if len(last_two_bottoms) == 2:
            price_diff = abs(last_two_bottoms[0] - last_two_bottoms[1])
            avg_price = (last_two_bottoms[0] + last_two_bottoms[1]) / 2
            if price_diff / avg_price < 0.02:  # 价差小于2%
                return True

        return False

    def _check_double_top(self, prices: np.ndarray) -> bool:
        """检测双顶形态"""
        peaks, _ = find_peaks(prices)  # 寻找高点
        if len(peaks) < 2:
            return False

        # 检查最后两个高点是否符合双顶特征
        last_two_tops = prices[peaks[-2:]]
        if len(last_two_tops) == 2:
            price_diff = abs(last_two_tops[0] - last_two_tops[1])
            avg_price = (last_two_tops[0] + last_two_tops[1]) / 2
            if price_diff / avg_price < 0.02:  # 价差小于2%
                return True

        return False

    def _analyze_trend_strength(self, prices: np.ndarray) -> Dict:
        """分析趋势强度"""
        # 计算价格变化率
        price_changes = np.diff(prices) / prices[:-1]

        # 计算趋势强度
        trend_strength = np.mean(price_changes) * 100

        if trend_strength > 0.5:
            return {'strength': 'strong_up', 'value': trend_strength}
        elif trend_strength > 0.1:
            return {'strength': 'weak_up', 'value': trend_strength}
        elif trend_strength < -0.5:
            return {'strength': 'strong_down', 'value': trend_strength}
        elif trend_strength < -0.1:
            return {'strength': 'weak_down', 'value': trend_strength}
        else:
            return {'strength': 'neutral', 'value': trend_strength}
