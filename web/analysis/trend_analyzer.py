class TrendAnalyzer:
    @staticmethod
    def analyze_ma_trend(mas):
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

    @staticmethod
    def analyze_macd(macd_data):
        """分析MACD"""
        macd, signal, hist = (
            macd_data['macd'],
            macd_data['signal'],
            macd_data['hist'],
        )

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
