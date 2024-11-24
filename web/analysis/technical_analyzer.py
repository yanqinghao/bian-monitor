from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
import talib
from analysis.indicators import TechnicalIndicators
from analysis.levels_finder import LevelsFinder
from analysis.pattern_detection import MarketCycle


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
        pattern_analysis: Dict = None,
        market_analysis: Dict = None,  # 新增市场分析参数
    ) -> List[Dict]:
        """
        改进的信号生成函数,加入市场周期分析

        Args:
            indicators: 技术指标数据
            price: 当前价格
            key_levels: 支撑阻力位
            volume_data: 成交量数据
            pattern_analysis: 形态分析结果
            market_analysis: 市场周期分析结果
        """
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

            # 分析形态的影响
            pattern_score = 0
            pattern_signal = 'neutral'
            if pattern_analysis and 'significant_patterns' in pattern_analysis:
                pattern_score, pattern_signal = self._evaluate_patterns(
                    pattern_analysis['significant_patterns'],
                    trend_alignment['trends'],
                )

            # 市场周期评估
            cycle_score = 0
            if market_analysis:
                cycle_score = self._evaluate_market_cycle(
                    market_analysis.get('market_cycle'),
                    market_analysis.get('trend_strength', 0),
                )

            # 综合评分 (调整权重分配)
            base_score = (
                technical_score_4h * 0.20
                + technical_score_1h * 0.15  # 降低权重
                + technical_score_15m * 0.10  # 降低权重
                + support_resistance_score * 0.20  # 保持不变
                + volume_score * 0.15  # 降低权重
                + pattern_score * 0.10  # 保持不变
                + cycle_score * 0.10  # 提高权重  # 新增市场周期权重
            )

            # 调整分数基于市场条件
            base_score = self._adjust_score_by_market_conditions(
                base_score, market_analysis, pattern_signal, trend_alignment
            )

            # 确定信号类型
            signal_type = self._determine_enhanced_signal_type(
                base_score=base_score,
                volume_score=volume_score,
                technical_scores={
                    '4h': technical_score_4h,
                    '1h': technical_score_1h,
                    '15m': technical_score_15m,
                },
                pattern_signal=pattern_signal,
                trend_aligned=trend_alignment['aligned'],
                market_cycle=market_analysis.get('market_cycle')
                if market_analysis
                else None,
                sr_score=support_resistance_score,
            )

            if signal_type:
                # 风险评估
                risk_assessment = self._assess_risk_level(
                    base_score=base_score,
                    sr_score=support_resistance_score,
                    volume_score=volume_score,
                    pattern_score=pattern_score,
                    market_analysis=market_analysis,
                )

                # 计算目标位和止损位
                entry_targets = self._calculate_entry_targets(
                    current_price=price,
                    signal_type=signal_type,
                    key_levels=key_levels,
                    market_analysis=market_analysis,
                )

                # 创建信号
                signal = {
                    'type': signal_type,
                    'score': base_score,
                    'price': price,
                    'technical_score': {
                        '4h': technical_score_4h,
                        '1h': technical_score_1h,
                        '15m': technical_score_15m,
                    },
                    'trend_alignment': trend_alignment['status'],
                    'sr_score': support_resistance_score,
                    'volume_score': volume_score,
                    'pattern_score': pattern_score,
                    'market_cycle_score': cycle_score,
                    'risk_assessment': risk_assessment,
                    'entry_targets': entry_targets,
                    'reason': self._generate_enhanced_signal_reason(
                        indicators=indicators,
                        key_levels=key_levels,
                        volume_data=volume_data,
                        signal_type=signal_type,
                        trend_alignment=trend_alignment,
                        pattern_analysis=pattern_analysis,
                        market_analysis=market_analysis,
                    ),
                }
                signals.append(signal)

            return signals

        except Exception as e:
            print(f'生成交易信号出错: {e}')
            return []

    def _generate_enhanced_signal_reason(
        self,
        indicators: Dict,
        key_levels: Dict,
        volume_data: Dict,
        signal_type: str,
        trend_alignment: Dict,
        pattern_analysis: Dict,
        market_analysis: Optional[Dict],
    ) -> str:
        """生成增强版信号原因"""
        reasons = []

        # 添加市场周期信息
        if market_analysis:
            cycle = market_analysis.get('market_cycle')
            if cycle:
                reasons.append(f'当前处于{cycle.value}')

            trend_strength = market_analysis.get('trend_strength', 0)
            if trend_strength > 0.7:
                reasons.append(f'趋势强度高({trend_strength:.2f})')
            elif trend_strength < 0.3:
                reasons.append(f'趋势强度弱({trend_strength:.2f})')

        # 添加形态分析
        if pattern_analysis and 'significant_patterns' in pattern_analysis:
            pattern_reasons = []
            for pattern in pattern_analysis['significant_patterns']:
                if pattern['reliability'] >= 4:
                    pattern_reasons.append(
                        f"{pattern['name']}({pattern['type']})"
                    )
            if pattern_reasons:
                reasons.append(f"关键形态: {', '.join(pattern_reasons)}")

        # 添加趋势一致性信息
        if trend_alignment['aligned']:
            reasons.append(f"多周期{trend_alignment['status']}")

        # 添加支撑位/阻力位信息
        if signal_type.endswith('buy'):
            supports = key_levels.get('supports', [])
            if supports:
                nearest_support = max(
                    [s for s in supports if s < indicators['current_price']],
                    default=None,
                )
                if nearest_support:
                    distance = (
                        (indicators['current_price'] - nearest_support)
                        / indicators['current_price']
                        * 100
                    )
                    if distance < 3:
                        reasons.append(f'接近支撑位{nearest_support:.2f}')
        else:
            resistances = key_levels.get('resistances', [])
            if resistances:
                nearest_resistance = min(
                    [
                        r
                        for r in resistances
                        if r > indicators['current_price']
                    ],
                    default=None,
                )
                if nearest_resistance:
                    distance = (
                        (nearest_resistance - indicators['current_price'])
                        / indicators['current_price']
                        * 100
                    )
                    if distance < 3:
                        reasons.append(f'接近阻力位{nearest_resistance:.2f}')

        # 添加价格突破/跌破信息
        if market_analysis and 'breakdown_breakout' in market_analysis:
            bb_info = market_analysis['breakdown_breakout']
            if bb_info['type'] == 'breakout' and bb_info['confirmation']:
                reasons.append(f"突破确认位{bb_info['level']:.2f}")
            elif bb_info['type'] == 'breakdown' and bb_info['confirmation']:
                reasons.append(f"跌破确认位{bb_info['level']:.2f}")

        # 添加成交量分析
        volume_ratio = volume_data.get('ratio', 1)
        pressure_ratio = volume_data.get('pressure_ratio', 1)

        if volume_ratio > 1.5:
            reasons.append(f'成交量放大{volume_ratio:.1f}倍')
            if pressure_ratio > 1.5 and signal_type.endswith('buy'):
                reasons.append('买方压力强势')
            elif pressure_ratio < 0.7 and signal_type.endswith('sell'):
                reasons.append('卖方压力强势')
        elif volume_ratio < 0.7:
            reasons.append(f'成交量萎缩{1/volume_ratio:.1f}倍')

        # 添加各时间周期的技术指标信息
        for timeframe in ['4h', '1h', '15m']:
            if timeframe in indicators:
                timeframe_reasons = self._get_enhanced_timeframe_reasons(
                    indicators[timeframe],
                    signal_type,
                    timeframe,
                    market_analysis,
                )
                reasons.extend(timeframe_reasons)

        return '，'.join(reasons) if reasons else '技术面综合信号'

    def _get_enhanced_timeframe_reasons(
        self,
        timeframe_data: Dict,
        signal_type: str,
        timeframe: str,
        market_analysis: Optional[Dict],
    ) -> List[str]:
        """获取增强版时间周期原因"""
        reasons = []

        # RSI分析
        if 'rsi' in timeframe_data:
            rsi = timeframe_data['rsi']
            if signal_type.endswith('buy'):
                if rsi < 30:
                    reasons.append(f'{timeframe} RSI超卖({rsi:.1f})')
                elif 30 <= rsi <= 40:
                    reasons.append(f'{timeframe} RSI低位({rsi:.1f})')
            elif signal_type.endswith('sell'):
                if rsi > 70:
                    reasons.append(f'{timeframe} RSI超买({rsi:.1f})')
                elif 60 <= rsi <= 70:
                    reasons.append(f'{timeframe} RSI高位({rsi:.1f})')

        # MACD分析
        if 'macd' in timeframe_data:
            macd = timeframe_data['macd']
            if signal_type.endswith('buy'):
                if macd['hist'] > 0 and macd['hist'] > macd['hist'].shift(1):
                    reasons.append(f'{timeframe} MACD金叉上扬')
                elif macd['hist'] > 0:
                    reasons.append(f'{timeframe} MACD金叉')
            elif signal_type.endswith('sell'):
                if macd['hist'] < 0 and macd['hist'] < macd['hist'].shift(1):
                    reasons.append(f'{timeframe} MACD死叉下行')
                elif macd['hist'] < 0:
                    reasons.append(f'{timeframe} MACD死叉')

        # KDJ分析
        if 'kdj' in timeframe_data:
            kdj = timeframe_data['kdj']
            if signal_type.endswith('buy'):
                if kdj['j'] < 20:
                    reasons.append(f'{timeframe} KDJ超卖')
                elif kdj['j'] > kdj['j'].shift(1) and kdj['j'] < 50:
                    reasons.append(f'{timeframe} KDJ低位上扬')
            elif signal_type.endswith('sell'):
                if kdj['j'] > 80:
                    reasons.append(f'{timeframe} KDJ超买')
                elif kdj['j'] < kdj['j'].shift(1) and kdj['j'] > 50:
                    reasons.append(f'{timeframe} KDJ高位下行')

        # MA分析
        if 'ma' in timeframe_data:
            ma_data = timeframe_data['ma']
            current_price = timeframe_data['close']

            # 检查均线多头/空头排列
            ma_keys = sorted(ma_data.keys())  # 短期到长期
            if all(
                ma_data[ma_keys[i]] > ma_data[ma_keys[i + 1]]
                for i in range(len(ma_keys) - 1)
            ):
                reasons.append(f'{timeframe} 均线多头排列')
            elif all(
                ma_data[ma_keys[i]] < ma_data[ma_keys[i + 1]]
                for i in range(len(ma_keys) - 1)
            ):
                reasons.append(f'{timeframe} 均线空头排列')

            # 检查价格与均线关系
            if current_price > ma_data[ma_keys[0]] and signal_type.endswith(
                'buy'
            ):
                reasons.append(f'{timeframe} 价格站上短期均线')
            elif current_price < ma_data[ma_keys[0]] and signal_type.endswith(
                'sell'
            ):
                reasons.append(f'{timeframe} 价格跌破短期均线')

        # 考虑市场周期
        if market_analysis and timeframe == '4h':
            cycle = market_analysis.get('market_cycle')
            if cycle:
                if cycle in [
                    MarketCycle.BULL,
                    MarketCycle.BULL_BREAKOUT,
                ] and signal_type.endswith('buy'):
                    reasons.append('符合大周期趋势')
                elif cycle in [
                    MarketCycle.BEAR,
                    MarketCycle.BEAR_BREAKDOWN,
                ] and signal_type.endswith('sell'):
                    reasons.append('符合大周期趋势')

        return reasons

    def update_signal_description(self, original_signal: Dict) -> Dict:
        """更新信号描述，使其更易读和实用"""
        signal = original_signal.copy()

        # 添加建议操作描述
        action_desc = {
            'strong_buy': '强力买入',
            'buy': '建议买入',
            'strong_sell': '强力卖出',
            'sell': '建议卖出',
        }
        signal['action_description'] = action_desc.get(signal['type'], '观望')

        # 添加详细分析
        analysis = []

        # 市场周期分析
        if 'market_cycle_score' in signal:
            cycle_strength = (
                '强'
                if signal['market_cycle_score'] > 70
                else ('中等' if signal['market_cycle_score'] > 40 else '弱')
            )
            analysis.append(f'市场周期强度: {cycle_strength}')

        # 技术分析汇总
        tech_scores = signal.get('technical_score', {})
        if tech_scores:
            avg_tech_score = sum(tech_scores.values()) / len(tech_scores)
            tech_strength = (
                '强势'
                if avg_tech_score > 70
                else ('中性' if avg_tech_score > 40 else '弱势')
            )
            analysis.append(f'技术面: {tech_strength}')

        # 成交量分析
        if 'volume_score' in signal:
            vol_desc = (
                '放量'
                if signal['volume_score'] > 70
                else ('正常' if signal['volume_score'] > 40 else '萎缩')
            )
            analysis.append(f'成交量: {vol_desc}')

        # 形态分析
        if 'pattern_score' in signal and signal['pattern_score'] > 60:
            analysis.append('形态确认')

        # 风险评估
        if 'risk_assessment' in signal:
            risk = signal['risk_assessment']
            risk_level_desc = {
                'extreme': '极高风险',
                'high': '高风险',
                'medium': '中等风险',
                'low': '低风险',
            }
            analysis.append(
                f"风险等级: {risk_level_desc.get(risk['level'], '未知')}"
            )

            # 添加首要风险因素
            if risk['factors']:
                analysis.append(f"主要风险: {risk['factors'][0]}")

        signal['detailed_analysis'] = ' | '.join(analysis)

        return signal

    def _calculate_entry_targets(
        self,
        current_price: float,
        signal_type: str,
        key_levels: Dict,
        market_analysis: Optional[Dict],
    ) -> Dict:
        """计算入场目标价和止损位"""
        targets = {'entry': [], 'stop_loss': None, 'take_profit': []}

        try:
            if signal_type in ['strong_buy', 'buy']:
                # 买入目标价
                if 'supports' in key_levels:
                    supports = [
                        s for s in key_levels['supports'] if s < current_price
                    ]
                    if supports:
                        # 第一目标价位：最近支撑位上方1%
                        target1 = supports[-1] * 1.01
                        # 第二目标价位：当前价格下方0.5%
                        target2 = current_price * 0.995
                        targets['entry'] = sorted([target1, target2])

                        # 止损位：最近支撑位下方1-2%
                        targets['stop_loss'] = supports[-1] * 0.98

                # 获利目标
                if 'resistances' in key_levels:
                    resistances = [
                        r
                        for r in key_levels['resistances']
                        if r > current_price
                    ]
                    if resistances:
                        # 设置多个获利目标
                        targets['take_profit'] = [
                            resistances[0],  # 第一阻力位
                            resistances[0] * 1.02,  # 阻力位上方2%
                        ]

            elif signal_type in ['strong_sell', 'sell']:
                # 卖出目标价
                if 'resistances' in key_levels:
                    resistances = [
                        r
                        for r in key_levels['resistances']
                        if r > current_price
                    ]
                    if resistances:
                        # 第一目标价位：最近阻力位下方1%
                        target1 = resistances[0] * 0.99
                        # 第二目标价位：当前价格上方0.5%
                        target2 = current_price * 1.005
                        targets['entry'] = sorted(
                            [target1, target2], reverse=True
                        )

                        # 止损位：最近阻力位上方1-2%
                        targets['stop_loss'] = resistances[0] * 1.02

                # 获利目标
                if 'supports' in key_levels:
                    supports = [
                        s for s in key_levels['supports'] if s < current_price
                    ]
                    if supports:
                        # 设置多个获利目标
                        targets['take_profit'] = [
                            supports[-1],  # 第一支撑位
                            supports[-1] * 0.98,  # 支撑位下方2%
                        ]

            # 根据市场周期调整目标位
            if market_analysis and 'market_cycle' in market_analysis:
                cycle = market_analysis['market_cycle']
                if cycle in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]:
                    # 牛市中设置更宽松的止损
                    if targets['stop_loss']:
                        targets['stop_loss'] *= 0.98
                elif cycle in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]:
                    # 熊市中设置更严格的止损
                    if targets['stop_loss']:
                        targets['stop_loss'] *= 1.02

        except Exception as e:
            print(f'计算目标价位失败: {e}')

        return targets

    def _determine_enhanced_signal_type(
        self,
        base_score: float,
        volume_score: float,
        technical_scores: Dict[str, float],
        pattern_signal: str,
        trend_aligned: bool,
        market_cycle: Optional[MarketCycle],
        sr_score: float,
    ) -> Optional[str]:
        """增强版信号类型判断"""
        # 检查市场周期限制
        if market_cycle in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]:
            if base_score > 60:  # 在熊市中提高做多门槛
                base_score *= 0.9
        elif market_cycle in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]:
            if base_score < 40:  # 在牛市中提高做空门槛
                base_score *= 1.1

        # 强力买入信号条件
        if (
            base_score >= 75
            and volume_score >= 65
            and technical_scores['4h'] >= 60
            and technical_scores['1h'] >= 60
            and trend_aligned
            and pattern_signal in ['bullish', 'neutral']
            and market_cycle
            not in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]
            and sr_score >= 60
        ):
            return 'strong_buy'

        # 买入信号条件
        elif (
            base_score >= 60
            and technical_scores['4h'] >= 55
            and technical_scores['1h'] >= 50
            and pattern_signal != 'bearish'
            and market_cycle != MarketCycle.BEAR_BREAKDOWN
            and sr_score >= 50
        ):
            return 'buy'

        # 强力卖出信号条件
        elif (
            base_score <= 25
            and volume_score >= 65
            and technical_scores['4h'] <= 40
            and technical_scores['1h'] <= 40
            and trend_aligned
            and pattern_signal in ['bearish', 'neutral']
            and market_cycle
            not in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]
            and sr_score >= 60
        ):
            return 'strong_sell'

        # 卖出信号条件
        elif (
            base_score <= 40
            and technical_scores['4h'] <= 45
            and technical_scores['1h'] <= 50
            and pattern_signal != 'bullish'
            and market_cycle != MarketCycle.BULL_BREAKOUT
            and sr_score >= 50
        ):
            return 'sell'

        return None

    def _evaluate_market_cycle(
        self, market_cycle: Optional[MarketCycle], trend_strength: float
    ) -> float:
        """评估市场周期得分"""
        if not market_cycle:
            return 50  # 默认中性分数

        # 基础周期分数
        cycle_scores = {
            MarketCycle.BULL: 70,
            MarketCycle.BEAR: 30,
            MarketCycle.CONSOLIDATION: 50,
            MarketCycle.BULL_BREAKOUT: 80,
            MarketCycle.BEAR_BREAKDOWN: 20,
        }

        base_score = cycle_scores.get(market_cycle, 50)

        # 根据趋势强度调整分数
        score_adjustment = (trend_strength - 0.5) * 20

        return max(0, min(100, base_score + score_adjustment))

    def _adjust_score_by_market_conditions(
        self,
        base_score: float,
        market_analysis: Optional[Dict],
        pattern_signal: str,
        trend_alignment: Dict,
    ) -> float:
        """根据市场条件调整分数"""
        score = base_score

        if market_analysis:
            market_cycle = market_analysis.get('market_cycle')
            trend_strength = market_analysis.get('trend_strength', 0)

            # 市场周期调整
            if market_cycle in [MarketCycle.BULL, MarketCycle.BULL_BREAKOUT]:
                if score > 50:  # 看多信号在牛市中加强
                    score *= 1.1
            elif market_cycle in [
                MarketCycle.BEAR,
                MarketCycle.BEAR_BREAKDOWN,
            ]:
                if score < 50:  # 看空信号在熊市中加强
                    score *= 1.1

            # 趋势强度调整
            if trend_strength > 0.7:
                score *= 1.1
            elif trend_strength < 0.3:
                score *= 0.9

        # 形态确认调整
        if pattern_signal != 'neutral':
            if (pattern_signal == 'bullish' and score > 50) or (
                pattern_signal == 'bearish' and score < 50
            ):
                score *= 1.1

        # 趋势一致性调整
        if trend_alignment.get('aligned', False):
            score *= 1.1
        else:
            score *= 0.9

        return max(0, min(100, score))

    def _evaluate_patterns(
        self, significant_patterns: List[Dict], trends: Dict
    ) -> Tuple[float, str]:
        """评估形态的重要性和方向"""
        if not significant_patterns:
            return 0, 'neutral'

        total_score = 0
        bullish_weight = 0
        bearish_weight = 0

        for pattern in significant_patterns:
            # 计算单个形态的权重
            weight = (
                pattern['reliability'] * 0.4
                + pattern['strength'] * 0.3
                + pattern['position_importance'] * 0.3
            ) * 20  # 转换到0-100分制

            # 根据方向累加权重
            if pattern['type'] == '上涨':
                bullish_weight += weight
            elif pattern['type'] == '下跌':
                bearish_weight += weight

            # 如果形态确认趋势，额外加分
            if pattern['confirms_trend']:
                weight *= 1.2

            total_score += weight

        # 确定信号方向
        if bullish_weight > bearish_weight * 1.5:
            signal = 'bullish'
        elif bearish_weight > bullish_weight * 1.5:
            signal = 'bearish'
        else:
            signal = 'neutral'

        # 标准化分数到0-100
        final_score = min(100, total_score / len(significant_patterns))

        return final_score, signal

    def _determine_signal_type(
        self,
        base_score: float,
        volume_score: float,
        technical_score_4h: float,
        technical_score_1h: float,
        pattern_signal: str,
        trend_aligned: bool,
    ) -> Optional[str]:
        """改进的信号类型判断"""
        if (
            base_score >= 80
            and volume_score >= 70
            and technical_score_4h >= 65
            and technical_score_1h >= 65
            and trend_aligned
            and pattern_signal == 'bullish'
        ):
            return 'strong_buy'

        elif (
            base_score >= 65
            and technical_score_4h >= 60
            and technical_score_1h >= 55
            and pattern_signal in ['bullish', 'neutral']
        ):
            return 'buy'

        elif (
            base_score <= 20
            and volume_score <= 30
            and technical_score_4h <= 35
            and technical_score_1h <= 35
            and trend_aligned
            and pattern_signal == 'bearish'
        ):
            return 'strong_sell'

        elif (
            base_score <= 35
            and technical_score_4h <= 40
            and technical_score_1h <= 45
            and pattern_signal in ['bearish', 'neutral']
        ):
            return 'sell'

        return None

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
        self,
        base_score: float,
        sr_score: float,
        volume_score: float,
        pattern_score: float = 0,
        market_analysis: Optional[Dict] = None,  # 添加市场分析参数
    ) -> Dict[str, Union[str, float, List[str]]]:
        """
        评估交易风险等级

        Args:
            base_score: 基础技术得分 (0-100)
            sr_score: 支撑压力位得分 (0-100)
            volume_score: 成交量得分 (0-100)
            pattern_score: 形态分析得分 (0-100)
            market_analysis: 市场分析结果(可选)

        Returns:
            Dict: {
                'level': str,  # 风险等级
                'score': float,  # 风险分数
                'factors': List[str],  # 风险因素
                'recommendations': List[str]  # 风险管理建议
            }
        """
        try:
            risk_factors = []
            risk_score = 50  # 基础风险分

            # 1. 技术面风险评估
            technical_risk = self._evaluate_technical_risk(
                base_score, sr_score, pattern_score
            )
            risk_score += technical_risk['score_impact']
            risk_factors.extend(technical_risk['factors'])

            # 2. 位置风险评估
            position_risk = self._evaluate_position_risk(
                sr_score, market_analysis
            )
            risk_score += position_risk['score_impact']
            risk_factors.extend(position_risk['factors'])

            # 3. 市场环境风险评估
            market_risk = self._evaluate_market_risk(
                volume_score, market_analysis
            )
            risk_score += market_risk['score_impact']
            risk_factors.extend(market_risk['factors'])

            # 标准化风险分数到0-100
            final_risk_score = max(0, min(100, risk_score))

            # 确定风险等级
            if final_risk_score >= 75:
                risk_level = 'extreme'
            elif final_risk_score >= 60:
                risk_level = 'high'
            elif final_risk_score >= 40:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            # 生成风险管理建议
            recommendations = self._generate_risk_recommendations(
                risk_level, risk_factors, market_analysis
            )

            return {
                'level': risk_level,
                'score': final_risk_score,
                'factors': risk_factors,
                'recommendations': recommendations,
            }

        except Exception as e:
            print(f'风险评估失败: {e}')
            return {
                'level': 'high',
                'score': 75,
                'factors': ['风险评估过程出错'],
                'recommendations': ['建议保持谨慎'],
            }

    def _evaluate_technical_risk(
        self, base_score: float, sr_score: float, pattern_score: float
    ) -> Dict:
        """评估技术面风险"""
        factors = []
        score_impact = 0

        # 基础分数风险
        if base_score < 40:
            factors.append('技术指标偏弱')
            score_impact += 10
        elif base_score > 80:
            factors.append('可能过度追涨')
            score_impact += 5

        # 支撑阻力位风险
        if sr_score < 30:
            factors.append('距离关键位置较远')
            score_impact += 10
        elif sr_score > 80:
            factors.append('接近关键阻力/支撑位')
            score_impact += 15

        # 形态风险
        if pattern_score < 40:
            factors.append('形态不明确')
            score_impact += 5

        return {'score_impact': score_impact, 'factors': factors}

    def _evaluate_position_risk(
        self, sr_score: float, market_analysis: Optional[Dict]
    ) -> Dict:
        """评估位置风险"""
        factors = []
        score_impact = 0

        if not market_analysis:
            return {'score_impact': 0, 'factors': []}

        # 检查是否接近关键位置
        sr_analysis = market_analysis.get('support_resistance', {})
        if sr_analysis:
            position = sr_analysis.get('position', 'neutral')

            if position == 'at_resistance':
                factors.append('处于强阻力位')
                score_impact += 20
            elif position == 'at_support':
                factors.append('处于关键支撑位')
                score_impact += 15
            elif position == 'closer_to_resistance':
                factors.append('接近阻力位')
                score_impact += 10

        # 检查市场周期位置
        if 'market_cycle' in market_analysis:
            cycle = market_analysis['market_cycle']
            if cycle == MarketCycle.BULL_BREAKOUT:
                factors.append('突破初期风险较大')
                score_impact += 15
            elif cycle == MarketCycle.BEAR_BREAKDOWN:
                factors.append('破位下跌风险较大')
                score_impact += 20

        return {'score_impact': score_impact, 'factors': factors}

    def _evaluate_market_risk(
        self, volume_score: float, market_analysis: Optional[Dict]
    ) -> Dict:
        """评估市场环境风险"""
        factors = []
        score_impact = 0

        # 成交量风险
        if volume_score < 30:
            factors.append('成交量严重不足')
            score_impact += 15
        elif volume_score > 80:
            factors.append('成交量异常放大')
            score_impact += 10

        if not market_analysis:
            return {'score_impact': score_impact, 'factors': factors}

        # 趋势强度风险
        trend_strength = market_analysis.get('trend_strength', 0)
        if trend_strength < 0.3:
            factors.append('趋势强度较弱')
            score_impact += 10
        elif trend_strength > 0.8:
            factors.append('趋势过热')
            score_impact += 15

        # 市场周期风险
        if 'market_cycle' in market_analysis:
            cycle = market_analysis['market_cycle']
            cycle_risks = {
                MarketCycle.BULL: 5,
                MarketCycle.BEAR: 15,
                MarketCycle.CONSOLIDATION: 10,
                MarketCycle.BULL_BREAKOUT: 20,
                MarketCycle.BEAR_BREAKDOWN: 25,
            }
            score_impact += cycle_risks.get(cycle, 0)
            if cycle in [MarketCycle.BEAR, MarketCycle.BEAR_BREAKDOWN]:
                factors.append('处于下跌周期')
            elif cycle == MarketCycle.CONSOLIDATION:
                factors.append('市场震荡整理')

        return {'score_impact': score_impact, 'factors': factors}

    def _generate_risk_recommendations(
        self,
        risk_level: str,
        risk_factors: List[str],
        market_analysis: Optional[Dict],
    ) -> List[str]:
        """生成风险管理建议"""
        recommendations = []

        # 基于风险等级的基础建议
        risk_level_recommendations = {
            'extreme': ['建议暂时观望', '如需操作建议降低仓位至20%以下', '设置严格止损'],
            'high': ['建议谨慎操作', '建议仓位不超过40%', '及时止损'],
            'medium': ['建议适中仓位', '做好风险控制'],
            'low': ['可以考虑正常仓位', '依然需要设置止损'],
        }

        recommendations.extend(risk_level_recommendations.get(risk_level, []))

        # 基于具体风险因素的建议
        if '成交量严重不足' in risk_factors:
            recommendations.append('建议等待成交量放大再入场')
        if '成交量异常放大' in risk_factors:
            recommendations.append('注意可能的虚假放量')
        if '处于强阻力位' in risk_factors:
            recommendations.append('建议等待突破确认')
        if '接近阻力位' in risk_factors:
            recommendations.append('注意可能的反转风险')

        # 基于市场周期的建议
        if market_analysis and 'market_cycle' in market_analysis:
            cycle = market_analysis['market_cycle']
            cycle_recommendations = {
                MarketCycle.BULL: ['可以适当持仓'],
                MarketCycle.BEAR: ['建议以防守为主'],
                MarketCycle.CONSOLIDATION: ['建议等待方向明确'],
                MarketCycle.BULL_BREAKOUT: ['可以考虑突破追踪'],
                MarketCycle.BEAR_BREAKDOWN: ['建议观望等待企稳'],
            }
            recommendations.extend(cycle_recommendations.get(cycle, []))

        return recommendations

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
        """改进成交量质量评估，适配深度数据"""
        score = 50

        try:
            # 获取5分钟周期的基础数据
            volume_ratio = volume_data.get('ratio', 1)
            pressure_ratio = volume_data.get('pressure_ratio', 1)

            # # 分析买卖压力
            # bid_volume = volume_data.get('bid_volume', 0)
            # ask_volume = volume_data.get('ask_volume', 0)

            # 成交量比率分析
            if volume_ratio > 5:  # 过度放量
                score += 15
            elif volume_ratio > 2:
                score += 25
            elif volume_ratio > 1.5:
                score += 15
            elif volume_ratio < 0.5:
                score -= 25
            elif volume_ratio < 0.7:
                score -= 15

            # 买卖压力分析
            if pressure_ratio > 3:  # 强烈买压
                score += 15
            elif pressure_ratio > 1.5:
                score += 25
            elif pressure_ratio > 1.2:
                score += 15
            elif pressure_ratio < 0.5:  # 强烈卖压
                score -= 25
            elif pressure_ratio < 0.8:
                score -= 15

            # 考虑成交量趋势
            volume_trend = volume_data.get('volume_trend', {})
            consecutive_increase = volume_trend.get('consecutive_increase', 0)
            total_increase = volume_trend.get('total_increase', 0)

            if consecutive_increase >= 3 and total_increase > 20:
                score += 10
            elif consecutive_increase >= 2 and total_increase > 10:
                score += 5

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
        pattern_analysis: Dict,
    ) -> str:
        """改进的信号原因生成"""
        reasons = []

        # 添加趋势一致性信息
        if trend_alignment['aligned']:
            reasons.append(f"多周期{trend_alignment['status']}")

        # 添加形态分析信息
        if pattern_analysis and 'significant_patterns' in pattern_analysis:
            pattern_reasons = []
            for pattern in pattern_analysis['significant_patterns']:
                if pattern['reliability'] >= 4:
                    pattern_reasons.append(
                        f"{pattern['name']}({pattern['type']})"
                    )
            if pattern_reasons:
                reasons.append(f"主要形态: {', '.join(pattern_reasons)}")

        # 添加各个时间周期的信号
        for timeframe in ['4h', '1h', '15m']:
            if timeframe in indicators:
                timeframe_reasons = self._get_timeframe_reasons(
                    indicators[timeframe], signal_type, timeframe
                )
                reasons.extend(timeframe_reasons)

        # 添加支撑/阻力位信息
        if signal_type.endswith('buy'):
            if 'supports' in key_levels:
                nearest_support = min(
                    (
                        s
                        for s in key_levels['supports']
                        if s < indicators['current_price']
                    ),
                    default=None,
                )
                if nearest_support:
                    distance = (
                        (indicators['current_price'] - nearest_support)
                        / indicators['current_price']
                        * 100
                    )
                    if distance < 3:
                        reasons.append(f'接近支撑位{nearest_support:.2f}')
        else:
            if 'resistances' in key_levels:
                nearest_resistance = max(
                    (
                        r
                        for r in key_levels['resistances']
                        if r > indicators['current_price']
                    ),
                    default=None,
                )
                if nearest_resistance:
                    distance = (
                        (nearest_resistance - indicators['current_price'])
                        / indicators['current_price']
                        * 100
                    )
                    if distance < 3:
                        reasons.append(f'接近阻力位{nearest_resistance:.2f}')

        # 成交量分析
        volume_ratio = volume_data.get('ratio', 1)
        pressure_ratio = volume_data.get('pressure_ratio', 1)
        if volume_ratio > 1.5 and signal_type.endswith('buy'):
            reasons.append(f'成交量放大{volume_ratio:.1f}倍')
            if pressure_ratio > 1.5:
                reasons.append('买方压力强势')
        elif volume_ratio < 0.7 and signal_type.endswith('sell'):
            reasons.append(f'成交量萎缩{1/volume_ratio:.1f}倍')
            if pressure_ratio < 0.7:
                reasons.append('卖方压力强势')

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
