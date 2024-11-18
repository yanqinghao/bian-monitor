from analysis.trend_analyzer import TrendAnalyzer
from analysis.levels_finder import LevelsFinder


def calculate_signal_strength(df, indicators, trend_stage):
    """计算综合信号强度"""
    weights = {
        'trend': 0.3,  # 趋势权重
        'momentum': 0.2,  # 动量权重
        'technical': 0.3,  # 技术指标权重
        'volume': 0.2,  # 成交量权重
    }

    scores = {'trend': 0, 'momentum': 0, 'technical': 0, 'volume': 0}

    # 1. 趋势得分
    ma20 = indicators['ma']['MA20'].iloc[-1]
    ma60 = indicators['ma']['MA60'].iloc[-1]
    current_price = df['Close'].iloc[-1]

    if current_price > ma20 and ma20 > ma60:
        scores['trend'] = 1.0
    elif current_price > ma20:
        scores['trend'] = 0.7
    elif current_price > ma60:
        scores['trend'] = 0.5
    else:
        scores['trend'] = 0.3

    # 2. 动量得分
    momentum = trend_stage['momentum']
    if momentum > 2:
        scores['momentum'] = 1.0
    elif momentum > 1:
        scores['momentum'] = 0.7
    elif momentum > 0:
        scores['momentum'] = 0.5
    else:
        scores['momentum'] = 0.3

    # 3. 技术指标得分
    # MACD
    macd_hist = indicators['macd']['hist'].iloc[-1]
    # RSI
    rsi = indicators['rsi'].iloc[-1]
    # KDJ
    j = indicators['kdj']['j'].iloc[-1]

    tech_score = 0
    # MACD得分
    if macd_hist > 0:
        tech_score += 0.4
    # RSI得分
    if 40 <= rsi <= 60:
        tech_score += 0.3
    elif 30 <= rsi <= 70:
        tech_score += 0.2
    # KDJ得分
    if 40 <= j <= 60:
        tech_score += 0.3
    elif 30 <= j <= 70:
        tech_score += 0.2

    scores['technical'] = tech_score

    # 4. 成交量得分
    volume = df['Volume'].iloc[-1]
    volume_ma = df['Volume'].rolling(20).mean().iloc[-1]
    volume_ratio = volume / volume_ma

    if volume_ratio > 1.5:
        scores['volume'] = 1.0
    elif volume_ratio > 1.2:
        scores['volume'] = 0.8
    elif volume_ratio > 1:
        scores['volume'] = 0.6
    elif volume_ratio > 0.8:
        scores['volume'] = 0.4
    else:
        scores['volume'] = 0.2

    # 计算加权得分
    final_score = sum(score * weights[key] for key, score in scores.items())

    return round(final_score, 2)


class ReportGenerator:
    @staticmethod
    def analyze_trend_stage(df, indicators):
        """分析趋势阶段"""
        momentum = df['Close'].pct_change(5).mean() * 100
        volatility = df['Close'].pct_change().std() * 100
        volume_ma = df['Volume'].rolling(20).mean()
        recent_volume = df['Volume'].tail(5).mean()
        volume_trend = (
            '放量'
            if recent_volume / volume_ma.iloc[-1] > 1.2
            else '缩量'
            if recent_volume / volume_ma.iloc[-1] < 0.8
            else '平稳'
        )

        # 判断趋势阶段
        rsi = indicators['rsi'].iloc[-1]
        if rsi > 60 and momentum > 0:
            stage = '上升趋势初期'
            desc = '突破盘整,开始上行'
        elif rsi < 40 and momentum < 0:
            stage = '下降趋势初期'
            desc = '开始回落,需要观察'
        else:
            stage = '震荡整理'
            desc = '区间震荡,等待方向'

        return {
            'stage': stage,
            'description': desc,
            'volume_trend': volume_trend,
            'momentum': momentum,
            'volatility': volatility,
        }

    @staticmethod
    def analyze_timeframe(df, indicators):
        """分析某个时间周期的指标"""
        ma_trend = TrendAnalyzer.analyze_ma_trend(indicators['ma'])
        macd_analysis = TrendAnalyzer.analyze_macd(indicators['macd'])

        # KDJ状态判断
        k = indicators['kdj']['k'].iloc[-1]
        d = indicators['kdj']['d'].iloc[-1]
        j = indicators['kdj']['j'].iloc[-1]
        # 判断KDJ状态
        kdj_status = '超买' if j > 80 else '超卖' if j < 20 else '中性'

        # 获取前一个周期的值
        k_prev = indicators['kdj']['k'].iloc[-2]
        d_prev = indicators['kdj']['d'].iloc[-2]
        # 判断金叉死叉
        if k > d and k_prev <= d_prev:
            kdj_cross = '金叉'
        elif k < d and k_prev >= d_prev:
            kdj_cross = '死叉'
        else:
            kdj_cross = '无'

        return {
            'ma_trend': ma_trend,
            'macd': macd_analysis,
            'kdj': {
                'cross': kdj_cross,
                'k': k,
                'd': d,
                'j': j,
                'status': kdj_status,
            },
        }

    @staticmethod
    def generate_signal_based_strategy(
        df, key_levels, trend_stage, indicators, volatility
    ):
        """基于信号强度生成交易策略"""
        # current_price = df['Close'].iloc[-1]

        # 计算信号强度
        signal_strength = calculate_signal_strength(
            df, indicators, trend_stage
        )

        # 基于信号强度确定策略
        if signal_strength >= 0.7:
            bias = '强势看多'
            direction = 'long'
            position = {'max': 50, 'step': 20}
        elif signal_strength >= 0.6:
            bias = '偏多'
            direction = 'long'
            position = {'max': 40, 'step': 15}
        elif signal_strength <= 0.3:
            bias = '强势看空'
            direction = 'short'
            position = {'max': 50, 'step': 20}
        elif signal_strength <= 0.4:
            bias = '偏空'
            direction = 'short'
            position = {'max': 40, 'step': 15}
        else:
            bias = '建议观望'
            direction = 'wait'
            position = {'max': 0, 'step': 0}

        # 生成入场点
        entry_points = []
        if direction == 'long':
            # 生成做多入场点
            for support in key_levels['supports']:
                entry_points.append(
                    {
                        'price': support,
                        'type': f'潜在回调做多 (价格回调到{support}获得支撑后)',
                        'strength': 'strong'
                        if signal_strength > 0.7
                        else 'medium',
                    }
                )
        elif direction == 'short':
            # 生成做空入场点
            for resistance in key_levels['resistances']:
                entry_points.append(
                    {
                        'price': resistance,
                        'type': f'潜在反弹做空 (价格反弹到{resistance}遇阻后)',
                        'strength': 'strong'
                        if signal_strength < 0.3
                        else 'medium',
                    }
                )
        else:
            # 观望模式的潜在入场点
            entry_points = [
                {
                    'price': key_levels['resistances'][0],
                    'type': f'潜在突破做多 (价格突破{key_levels["resistances"][0]}并有效确认后)',
                    'strength': 'medium',
                },
                {
                    'price': key_levels['supports'][0],
                    'type': f'潜在回调做多 (价格回调到{key_levels["supports"][0]}获得支撑后)',
                    'strength': 'medium',
                },
                {
                    'price': key_levels['supports'][1],
                    'type': f'潜在回调做多 (价格回调到{key_levels["supports"][1]}获得支撑后)',
                    'strength': 'medium',
                },
            ]

        # 确保只返回前三个入场点
        entry_points = entry_points[:3]

        # 生成止损点
        stops = []
        for entry in entry_points:
            stop_price = LevelsFinder.calculate_stop_loss(
                entry_price=entry['price'],
                direction='long',
                volatility=volatility,
            )
            risk_percent = abs(
                (stop_price - entry['price']) / entry['price'] * 100
            )

            stops.append(
                {
                    'price': stop_price,
                    'type': '预设止损 (做多)',
                    'risk': f'{risk_percent:.1f}%',
                }
            )

        return {
            'bias': bias,
            'direction': direction,
            'signal_strength': signal_strength,
            'position': position,
            'entry_points': entry_points,
            'stops': stops,
        }
