from typing import Dict, List, Tuple
import pandas as pd
import talib
from analysis.indicators import TechnicalIndicators
from analysis.levels_finder import LevelsFinder


class TechnicalAnalyzer:
    def __init__(self):
        # Initialize TechnicalIndicators instance
        self.indicator_calculator = TechnicalIndicators()
        self.levels_finder = LevelsFinder()

    def calculate_indicators(
        self,
        kline_data_4h: List[Dict],
        kline_data_1h: List[Dict],
        kline_data_15m: List[Dict] = None,
    ) -> Dict:
        """Calculate indicators for 4h, 1h and 15m timeframes"""
        # 处理4小时数据
        df_4h = pd.DataFrame(kline_data_4h)
        df_4h.columns = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']
        indicators_4h = self.indicator_calculator.calculate_indicators(df_4h)
        volatility_4h = self.indicator_calculator.calculate_volatility_metrics(
            df_4h
        )

        # 处理1小时数据
        df_1h = pd.DataFrame(kline_data_1h)
        df_1h.columns = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']
        indicators_1h = self.indicator_calculator.calculate_indicators(df_1h)
        volatility_1h = self.indicator_calculator.calculate_volatility_metrics(
            df_1h
        )

        formatted_indicators = {
            'current_price': df_1h['Close'].iloc[-1],
            '4h': self._format_timeframe_indicators(
                df_4h, indicators_4h, volatility_4h
            ),
            '1h': self._format_timeframe_indicators(
                df_1h, indicators_1h, volatility_1h
            ),
        }

        # 处理15分钟数据(如果有)
        if kline_data_15m:
            df_15m = pd.DataFrame(kline_data_15m)
            df_15m.columns = [
                'Open time',
                'Open',
                'High',
                'Low',
                'Close',
                'Volume',
            ]
            indicators_15m = self.indicator_calculator.calculate_indicators(
                df_15m
            )
            volatility_15m = (
                self.indicator_calculator.calculate_volatility_metrics(df_15m)
            )
            formatted_indicators['15m'] = self._format_timeframe_indicators(
                df_15m, indicators_15m, volatility_15m
            )

        return formatted_indicators

    def _format_timeframe_indicators(
        self, df: pd.DataFrame, indicators: Dict, volatility: Dict
    ) -> Dict:
        """Format indicators for a specific timeframe"""
        return {
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

    def _calculate_timeframe_score(self, timeframe_data: Dict) -> float:
        """Calculate score for a single timeframe"""
        score = 50

        # RSI分析
        if 'rsi' in timeframe_data and timeframe_data['rsi'] is not None:
            rsi = timeframe_data['rsi']
            if rsi < 30:
                score += 20 * (30 - rsi) / 30
            elif rsi > 70:
                score -= 20 * (rsi - 70) / 30
            elif 40 <= rsi <= 60:
                score += 10

        # MACD分析
        if 'macd' in timeframe_data:
            macd = timeframe_data['macd']
            if all(v is not None for v in macd.values()):
                if macd['hist'] > 0:
                    score += min(15, abs(macd['hist']) * 100)
                else:
                    score -= min(15, abs(macd['hist']) * 100)

        # KDJ分析
        if 'kdj' in timeframe_data:
            kdj = timeframe_data['kdj']
            if kdj['j'] < 20:
                score += 15
            elif kdj['j'] > 80:
                score -= 15

        # 趋势分析
        if 'trend' in timeframe_data:
            trend = timeframe_data['trend']
            score += (trend['strength'] - 50) * 0.3

        # 波动性分析
        if 'volatility' in timeframe_data:
            vol = timeframe_data['volatility']
            if vol.get('atr_percent', 0) > 5:
                score -= 10

        return max(0, min(100, score))

    def _calculate_technical_score(
        self, indicators: Dict
    ) -> Tuple[float, float, float]:
        """Calculate technical scores for all timeframes"""
        score_4h = 50
        score_1h = 50
        score_15m = 50

        try:
            if '4h' in indicators:
                score_4h = self._calculate_timeframe_score(indicators['4h'])
            if '1h' in indicators:
                score_1h = self._calculate_timeframe_score(indicators['1h'])
            if '15m' in indicators:
                score_15m = self._calculate_timeframe_score(indicators['15m'])

            return score_4h, score_1h, score_15m

        except Exception as e:
            print(f'计算技术得分出错: {e}')
            return 50, 50, 50

    def generate_trading_signals(
        self,
        indicators: Dict,
        price: float,
        key_levels: Dict,
        volume_data: Dict,
    ) -> List[Dict]:
        """Generate trading signals with multi-timeframe analysis"""
        signals = []

        try:
            # 计算三个时间周期的技术分
            (
                technical_score_4h,
                technical_score_1h,
                technical_score_15m,
            ) = self._calculate_technical_score(indicators)

            # 支撑/阻力分数
            support_resistance_score = self._evaluate_sr_score(
                price, key_levels
            )

            # 成交量分数
            volume_score = self._evaluate_volume_quality(volume_data)

            # 趋势一致性检查
            trend_alignment = self._check_trend_alignment(indicators)

            # 综合评分 (4h:25%, 1h:20%, 15m:10%, 支撑阻力:25%, 成交量:20%)
            total_score = (
                technical_score_4h * 0.25
                + technical_score_1h * 0.20
                + technical_score_15m * 0.10
                + support_resistance_score * 0.25
                + volume_score * 0.20
            )

            # 加入趋势一致性奖励/惩罚
            if trend_alignment['aligned']:
                total_score *= 1.1  # 趋势一致性奖励
            else:
                total_score *= 0.9  # 趋势不一致惩罚
            # 信号判断 (同时考虑趋势一致性)
            if (
                total_score >= 80
                and volume_score >= 70
                and technical_score_4h >= 65
                and technical_score_1h >= 65
                and trend_alignment['aligned']
            ):
                signal_type = 'strong_buy'
            elif (
                total_score >= 65
                and technical_score_4h >= 60
                and technical_score_1h >= 55
            ):
                signal_type = 'buy'
            elif (
                total_score <= 20
                and volume_score <= 30
                and technical_score_4h <= 35
                and technical_score_1h <= 35
                and trend_alignment['aligned']
            ):
                signal_type = 'strong_sell'
            elif (
                total_score <= 35
                and technical_score_4h <= 40
                and technical_score_1h <= 45
            ):
                signal_type = 'sell'
            else:
                return []

            signals.append(
                {
                    'type': signal_type,
                    'score': total_score,
                    'price': price,
                    'technical_score': {
                        '4h': technical_score_4h,
                        '1h': technical_score_1h,
                        '15m': technical_score_15m,
                    },
                    'trend_alignment': trend_alignment['status'],
                    'sr_score': support_resistance_score,
                    'volume_score': volume_score,
                    'risk_level': self._assess_risk_level(
                        (
                            technical_score_4h * 0.4
                            + technical_score_1h * 0.4
                            + technical_score_15m * 0.2
                        ),
                        support_resistance_score,
                        volume_score,
                    ),
                    'reason': self._generate_signal_reason(
                        indicators,
                        key_levels,
                        volume_data,
                        signal_type,
                        trend_alignment,
                    ),
                }
            )

        except Exception as e:
            print(f'生成交易信号出错: {e}')

        return signals

    def _check_trend_alignment(self, indicators: Dict) -> Dict:
        """检查不同时间周期趋势是否一致"""
        trends = {}
        for timeframe in ['4h', '1h', '15m']:
            if timeframe in indicators:
                trends[timeframe] = indicators[timeframe]['trend']['direction']

        # 检查趋势一致性
        if len(trends) >= 2:
            main_trend = trends.get('4h', trends.get('1h', None))
            aligned = all(trend == main_trend for trend in trends.values())

            if aligned:
                status = f'趋势一致({main_trend})'
            else:
                status = '趋势分歧'

            return {'aligned': aligned, 'status': status, 'trends': trends}

        return {'aligned': False, 'status': '数据不足', 'trends': trends}

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
        trend_alignment: Dict,
    ) -> str:
        """Generate detailed signal reason with multi-timeframe analysis"""
        reasons = []

        # 添加趋势一致性信息
        if trend_alignment['aligned']:
            reasons.append(f"多周期{trend_alignment['status']}")

        # 各个时间周期的信号
        for timeframe in ['4h', '1h', '15m']:
            if timeframe in indicators:
                timeframe_reasons = self._get_timeframe_reasons(
                    indicators[timeframe], signal_type, timeframe
                )
                reasons.extend(timeframe_reasons)

        # 成交量分析
        volume_ratio = volume_data.get('ratio', 1)
        if volume_ratio > 1.5 and signal_type.endswith('buy'):
            reasons.append(f'成交量放大{volume_ratio:.1f}倍')
        elif volume_ratio < 0.7 and signal_type.endswith('sell'):
            reasons.append(f'成交量萎缩{1/volume_ratio:.1f}倍')

        return '，'.join(reasons) if reasons else '技术面综合信号'

    def _get_timeframe_reasons(
        self, timeframe_data: Dict, signal_type: str, timeframe: str
    ) -> List[str]:
        """Get reasons for a specific timeframe"""
        reasons = []

        # RSI
        if 'rsi' in timeframe_data:
            rsi = timeframe_data['rsi']
            if rsi < 30 and signal_type.endswith('buy'):
                reasons.append(f'{timeframe} RSI超卖({rsi:.1f})')
            elif rsi > 70 and signal_type.endswith('sell'):
                reasons.append(f'{timeframe} RSI超买({rsi:.1f})')

        # MACD
        if 'macd' in timeframe_data:
            macd = timeframe_data['macd']
            if macd['hist'] > 0 and signal_type.endswith('buy'):
                reasons.append(f'{timeframe} MACD金叉')
            elif macd['hist'] < 0 and signal_type.endswith('sell'):
                reasons.append(f'{timeframe} MACD死叉')

        # KDJ
        if 'kdj' in timeframe_data:
            kdj = timeframe_data['kdj']
            if kdj['j'] < 20 and signal_type.endswith('buy'):
                reasons.append(f'{timeframe} KDJ超卖')
            elif kdj['j'] > 80 and signal_type.endswith('sell'):
                reasons.append(f'{timeframe} KDJ超买')

        return reasons
