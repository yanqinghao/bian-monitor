from typing import Dict, List
import pandas as pd
import talib
from analysis.indicators import TechnicalIndicators
from analysis.levels_finder import LevelsFinder


class TechnicalAnalyzer:
    def __init__(self):
        # Initialize TechnicalIndicators instance
        self.indicator_calculator = TechnicalIndicators()
        self.levels_finder = LevelsFinder()

    def calculate_indicators(self, kline_data: List[Dict]) -> Dict:
        """优化指标计算，增加更多时间周期"""
        df = pd.DataFrame(kline_data)
        df.columns = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']

        # 基础指标计算
        indicators = self.indicator_calculator.calculate_indicators(df)
        volatility = self.indicator_calculator.calculate_volatility_metrics(df)

        # 格式化结果并添加更多指标
        formatted_indicators = {
            'current_price': df['Close'].iloc[-1],
            'rsi': indicators['rsi'].iloc[-1]
            if len(indicators['rsi']) > 0
            else None,
            'macd': {
                'macd': indicators['macd']['macd'].iloc[-1],
                'signal': indicators['macd']['signal'].iloc[-1],
                'hist': indicators['macd']['hist'].iloc[-1],
            },
            'kdj': {
                'k': indicators['kdj']['k'].iloc[-1],
                'd': indicators['kdj']['d'].iloc[-1],
                'j': indicators['kdj']['j'].iloc[-1],
            },
            'ma': {
                period: values.iloc[-1]
                for period, values in indicators['ma'].items()
            },
            'volatility': {
                'atr_percent': volatility['atr_percent'].iloc[-1],
                'returns_vol': volatility['returns_volatility'],
                'keltner': self._calculate_keltner_channels(df),
                'price_volatility': self._calculate_price_volatility(df),
            },
            'trend': self._analyze_trend(df),
        }

        return formatted_indicators

    def _calculate_price_volatility(self, df: pd.DataFrame) -> Dict:
        """计算价格波动特征"""
        try:
            returns = df['Close'].pct_change()
            high_low_ratio = df['High'] / df['Low']

            return {
                'returns_std': returns.std(),
                'high_low_ratio': high_low_ratio.mean(),
                'price_range': (df['High'].max() - df['Low'].min())
                / df['Close'].mean(),
            }
        except Exception as e:
            print(f'计算价格波动特征失败: {e}')
            return {}

    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """分析趋势特征"""
        try:
            close = df['Close'].values
            ma5 = talib.SMA(close, timeperiod=5)
            ma10 = talib.SMA(close, timeperiod=10)
            ma20 = talib.SMA(close, timeperiod=20)

            current_price = close[-1]
            trend_strength = 0

            # 计算趋势强度
            if current_price > ma5[-1] > ma10[-1] > ma20[-1]:
                trend_strength = 100
            elif current_price > ma5[-1] > ma10[-1]:
                trend_strength = 75
            elif current_price > ma5[-1]:
                trend_strength = 50
            elif current_price < ma5[-1] < ma10[-1] < ma20[-1]:
                trend_strength = 0
            elif current_price < ma5[-1] < ma10[-1]:
                trend_strength = 25

            return {
                'strength': trend_strength,
                'direction': 'up' if trend_strength > 50 else 'down',
                'ma_alignment': trend_strength >= 75,
            }
        except Exception as e:
            print(f'分析趋势失败: {e}')
            return {
                'strength': 50,
                'direction': 'neutral',
                'ma_alignment': False,
            }

    def _calculate_keltner_channels(self, df: pd.DataFrame) -> Dict:
        """计算肯特纳通道"""
        try:
            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            ma20 = talib.EMA(typical_price, timeperiod=20)
            atr = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=20)

            upper = ma20 + (2 * atr)
            lower = ma20 - (2 * atr)

            return {
                'upper': upper.iloc[-1],
                'middle': ma20.iloc[-1],
                'lower': lower.iloc[-1],
            }
        except Exception as e:
            print(f'计算肯特纳通道失败: {e}')
            return {'upper': 0, 'middle': 0, 'lower': 0}

    def analyze_key_levels(
        self, df: pd.DataFrame, current_price: float
    ) -> Dict:
        """Wrapper for LevelsFinder's key levels analysis"""
        return self.levels_finder.find_key_levels(df, current_price)

    def _calculate_technical_score(self, indicators: Dict) -> float:
        """改进技术得分计算"""
        score = 50

        try:
            # RSI分析
            if 'rsi' in indicators and indicators['rsi'] is not None:
                rsi = indicators['rsi']
                if rsi < 30:
                    score += 20 * (30 - rsi) / 30
                elif rsi > 70:
                    score -= 20 * (rsi - 70) / 30
                elif 40 <= rsi <= 60:  # 添加中性区间判断
                    score += 10

            # MACD分析
            if 'macd' in indicators:
                macd = indicators['macd']
                if all(v is not None for v in macd.values()):
                    if macd['hist'] > 0:
                        score += min(15, abs(macd['hist']) * 100)  # 降低MACD的权重
                    else:
                        score -= min(15, abs(macd['hist']) * 100)

            # KDJ分析
            if 'kdj' in indicators and all(
                v is not None for v in indicators['kdj'].values()
            ):
                kdj = indicators['kdj']
                if kdj['j'] < 20:
                    score += 15
                elif kdj['j'] > 80:
                    score -= 15

            # 趋势分析
            if 'trend' in indicators:
                trend = indicators['trend']
                score += (trend['strength'] - 50) * 0.3  # 添加趋势影响

            # 波动性分析
            if 'volatility' in indicators:
                vol = indicators['volatility']
                if vol.get('atr_percent', 0) > 5:  # 高波动性降分
                    score -= 10

            return max(0, min(100, score))

        except Exception as e:
            print(f'计算技术得分出错: {e}')
            return 50

    def generate_trading_signals(
        self,
        indicators: Dict,
        price: float,
        key_levels: Dict,
        volume_data: Dict,
    ) -> List[Dict]:
        """改进信号生成逻辑"""
        signals = []

        try:
            # 计算各维度得分
            technical_score = self._calculate_technical_score(indicators)
            support_resistance_score = self._evaluate_sr_score(
                price, key_levels
            )
            volume_score = self._evaluate_volume_quality(volume_data)

            # 调整权重计算
            total_score = (
                technical_score * 0.45
                + support_resistance_score * 0.30  # 降低技术面权重
                + volume_score * 0.25  # 提高成交量权重
            )

            # 确定信号类型
            if total_score >= 80 and volume_score >= 70:  # 提高强买要求
                signal_type = 'strong_buy'
            elif total_score >= 65:
                signal_type = 'buy'
            elif total_score <= 20 and volume_score <= 30:
                signal_type = 'strong_sell'
            elif total_score <= 35:
                signal_type = 'sell'
            else:
                return []

            signals.append(
                {
                    'type': signal_type,
                    'score': total_score,
                    'price': price,
                    'technical_score': technical_score,
                    'sr_score': support_resistance_score,
                    'volume_score': volume_score,
                    'risk_level': self._assess_risk_level(
                        technical_score, support_resistance_score, volume_score
                    ),
                    'reason': self._generate_signal_reason(
                        indicators, key_levels, volume_data, signal_type
                    ),
                }
            )

            return signals

        except Exception as e:
            print(f'生成交易信号出错: {e}')
            return []

    def _assess_risk_level(
        self, technical_score: float, sr_score: float, volume_score: float
    ) -> str:
        """评估风险等级"""
        try:
            # 计算综合风险分数
            risk_score = (
                (100 - technical_score) * 0.4
                + (100 - sr_score) * 0.3
                + (100 - volume_score) * 0.3
            )

            if risk_score >= 70:
                return 'high'
            elif risk_score >= 40:
                return 'medium'
            else:
                return 'low'

        except Exception as e:
            print(f'评估风险等级出错: {e}')
            return 'high'  # 出错时返回高风险

    def _evaluate_sr_score(self, price: float, key_levels: Dict) -> float:
        """Evaluates support/resistance score"""
        score = 50

        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])

        # Check support levels
        if supports:
            nearest_support = min(supports, key=lambda x: abs(x - price))
            distance_to_support = abs(price - nearest_support) / price
            if distance_to_support <= 0.01:  # Within 1%
                score += 30
            elif distance_to_support <= 0.02:  # Within 2%
                score += 20

        # Check resistance levels
        if resistances:
            nearest_resistance = min(resistances, key=lambda x: abs(x - price))
            distance_to_resistance = abs(price - nearest_resistance) / price
            if distance_to_resistance <= 0.01:
                score -= 30
            elif distance_to_resistance <= 0.02:
                score -= 20

        return max(0, min(100, score))

    def _evaluate_volume_quality(self, volume_data: Dict) -> float:
        """改进成交量质量评估"""
        score = 50

        try:
            volume_ratio = volume_data.get('ratio', 1)
            pressure_ratio = volume_data.get('pressure_ratio', 1)

            # 成交量比率分析
            if volume_ratio > 5:  # 过度放量
                score += 15  # 降低极端放量的得分
            elif volume_ratio > 2:
                score += 25
            elif volume_ratio > 1.5:
                score += 15
            elif volume_ratio < 0.5:
                score -= 25
            elif volume_ratio < 0.7:
                score -= 15

            # 买卖压力分析
            if pressure_ratio > 3:  # 过度买压
                score += 15  # 降低极端买压的得分
            elif pressure_ratio > 1.5:
                score += 25
            elif pressure_ratio > 1.2:
                score += 15
            elif pressure_ratio < 0.5:
                score -= 25
            elif pressure_ratio < 0.8:
                score -= 15

            return max(0, min(100, score))

        except Exception as e:
            print(f'评估成交量质量出错: {e}')
            return 50

    def _generate_signal_reason(
        self,
        indicators: Dict,
        key_levels: Dict,
        volume_data: Dict,
        signal_type: str,
    ) -> str:
        """Generates detailed reason for the signal"""
        reasons = []

        # Technical indicators
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30 and signal_type.endswith('buy'):
                reasons.append(f'RSI超卖({rsi:.1f})')
            elif rsi > 70 and signal_type.endswith('sell'):
                reasons.append(f'RSI超买({rsi:.1f})')

        # MACD
        if 'macd' in indicators:
            macd = indicators['macd']
            if macd['hist'] > 0 and signal_type.endswith('buy'):
                reasons.append('MACD金叉')
            elif macd['hist'] < 0 and signal_type.endswith('sell'):
                reasons.append('MACD死叉')

        # Volume
        volume_ratio = volume_data.get('ratio', 1)
        if volume_ratio > 1.5 and signal_type.endswith('buy'):
            reasons.append(f'成交量放大{volume_ratio:.1f}倍')
        elif volume_ratio < 0.7 and signal_type.endswith('sell'):
            reasons.append(f'成交量萎缩{1/volume_ratio:.1f}倍')

        return '，'.join(reasons) if reasons else '技术面综合信号'
