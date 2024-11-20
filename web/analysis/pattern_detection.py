import talib
import pandas as pd
from typing import Dict, List, Union


class PatternDetection:
    """K线形态识别类"""

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        检测常见K线形态
        返回一个字典，包含各种K线形态的信号序列
        信号值：
        100 = 看涨形态
        -100 = 看跌形态
        0 = 无形态
        """
        patterns = {}

        # 单根K线形态
        patterns['DOJI'] = talib.CDLDOJI(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['HAMMER'] = talib.CDLHAMMER(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['SHOOTING_STAR'] = talib.CDLSHOOTINGSTAR(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['SPINNING_TOP'] = talib.CDLSPINNINGTOP(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['MARUBOZU'] = talib.CDLMARUBOZU(
            df['Open'], df['High'], df['Low'], df['Close']
        )

        # 两根K线形态
        patterns['ENGULFING'] = talib.CDLENGULFING(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['HARAMI'] = talib.CDLHARAMI(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['PIERCING'] = talib.CDLPIERCING(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['DARK_CLOUD_COVER'] = talib.CDLDARKCLOUDCOVER(
            df['Open'], df['High'], df['Low'], df['Close']
        )

        # 三根K线形态
        patterns['MORNING_STAR'] = talib.CDLMORNINGSTAR(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['EVENING_STAR'] = talib.CDLEVENINGSTAR(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['THREE_WHITE_SOLDIERS'] = talib.CDL3WHITESOLDIERS(
            df['Open'], df['High'], df['Low'], df['Close']
        )
        patterns['THREE_BLACK_CROWS'] = talib.CDL3BLACKCROWS(
            df['Open'], df['High'], df['Low'], df['Close']
        )

        return patterns

    @staticmethod
    def detect_price_patterns(
        df: pd.DataFrame, window: int = 20
    ) -> Dict[str, pd.Series]:
        """检测价格形态"""
        patterns = {}

        # 双底形态检测
        patterns['DOUBLE_BOTTOM'] = PatternDetection._detect_double_bottom(
            df, window
        )

        # 双顶形态检测
        patterns['DOUBLE_TOP'] = PatternDetection._detect_double_top(
            df, window
        )

        # 头肩顶形态检测
        patterns[
            'HEAD_AND_SHOULDERS'
        ] = PatternDetection._detect_head_and_shoulders(df, window)

        # 头肩底形态检测
        patterns[
            'INVERSE_HEAD_AND_SHOULDERS'
        ] = PatternDetection._detect_inverse_head_and_shoulders(df, window)

        return patterns

    @staticmethod
    def _detect_double_bottom(df: pd.DataFrame, window: int = 20) -> pd.Series:
        """双底形态检测"""
        pattern = pd.Series(0, index=df.index)
        prices = df['Close'].values

        for i in range(window, len(prices) - window):
            window_prices = prices[i - window : i + window]
            if len(window_prices) < 2 * window:
                continue

            # 找到局部最小值
            valleys = []
            for j in range(1, len(window_prices) - 1):
                if (
                    window_prices[j] < window_prices[j - 1]
                    and window_prices[j] < window_prices[j + 1]
                ):
                    valleys.append((j, window_prices[j]))

            # 检查是否有两个相近的谷底
            if len(valleys) >= 2:
                for v1_idx in range(len(valleys) - 1):
                    for v2_idx in range(v1_idx + 1, len(valleys)):
                        v1, v2 = valleys[v1_idx], valleys[v2_idx]
                        # 检查两个谷底的价格是否相近（允许5%的误差）
                        price_diff = abs(v1[1] - v2[1]) / v1[1]
                        if price_diff < 0.05 and (v2[0] - v1[0]) > window // 2:
                            pattern.iloc[i] = 100

        return pattern

    @staticmethod
    def _detect_double_top(df: pd.DataFrame, window: int = 20) -> pd.Series:
        """双顶形态检测"""
        pattern = pd.Series(0, index=df.index)
        prices = df['Close'].values

        for i in range(window, len(prices) - window):
            window_prices = prices[i - window : i + window]
            if len(window_prices) < 2 * window:
                continue

            # 找到局部最大值
            peaks = []
            for j in range(1, len(window_prices) - 1):
                if (
                    window_prices[j] > window_prices[j - 1]
                    and window_prices[j] > window_prices[j + 1]
                ):
                    peaks.append((j, window_prices[j]))

            # 检查是否有两个相近的顶点
            if len(peaks) >= 2:
                for p1_idx in range(len(peaks) - 1):
                    for p2_idx in range(p1_idx + 1, len(peaks)):
                        p1, p2 = peaks[p1_idx], peaks[p2_idx]
                        # 检查两个顶点的价格是否相近（允许5%的误差）
                        price_diff = abs(p1[1] - p2[1]) / p1[1]
                        if price_diff < 0.05 and (p2[0] - p1[0]) > window // 2:
                            pattern.iloc[i] = -100

        return pattern

    @staticmethod
    def _detect_head_and_shoulders(
        df: pd.DataFrame, window: int = 20
    ) -> pd.Series:
        """头肩顶形态检测"""
        pattern = pd.Series(0, index=df.index)
        prices = df['Close'].values

        for i in range(window, len(prices) - window):
            window_prices = prices[i - window : i + window]
            if len(window_prices) < 2 * window:
                continue

            # 找到局部最大值
            peaks = []
            for j in range(1, len(window_prices) - 1):
                if (
                    window_prices[j] > window_prices[j - 1]
                    and window_prices[j] > window_prices[j + 1]
                ):
                    peaks.append((j, window_prices[j]))

            # 需要至少三个峰值
            if len(peaks) >= 3:
                for p1_idx in range(len(peaks) - 2):
                    p1 = peaks[p1_idx]
                    for p2_idx in range(p1_idx + 1, len(peaks) - 1):
                        p2 = peaks[p2_idx]
                        for p3_idx in range(p2_idx + 1, len(peaks)):
                            p3 = peaks[p3_idx]

                            # 检查是否符合头肩顶形态
                            if (
                                abs(p1[1] - p3[1]) / p1[1] < 0.05
                                and p2[1] > p1[1] * 1.1  # 左右肩高度相近
                                and p2[1] > p3[1] * 1.1
                                and p2[0] - p1[0] > window // 4  # 头部明显高于两肩
                                and p3[0] - p2[0] > window // 4  # 确保峰值之间有足够距离
                            ):

                                # 检查颈线水平
                                neckline1 = min(window_prices[p1[0] : p2[0]])
                                neckline2 = min(window_prices[p2[0] : p3[0]])
                                if (
                                    abs(neckline1 - neckline2) / neckline1
                                    < 0.03
                                ):  # 颈线较为水平
                                    pattern.iloc[i] = -100

        return pattern

    @staticmethod
    def _detect_inverse_head_and_shoulders(
        df: pd.DataFrame, window: int = 20
    ) -> pd.Series:
        """头肩底形态检测"""
        pattern = pd.Series(0, index=df.index)
        prices = df['Close'].values

        for i in range(window, len(prices) - window):
            window_prices = prices[i - window : i + window]
            if len(window_prices) < 2 * window:
                continue

            # 找到局部最小值
            valleys = []
            for j in range(1, len(window_prices) - 1):
                if (
                    window_prices[j] < window_prices[j - 1]
                    and window_prices[j] < window_prices[j + 1]
                ):
                    valleys.append((j, window_prices[j]))

            # 需要至少三个谷值
            if len(valleys) >= 3:
                for v1_idx in range(len(valleys) - 2):
                    v1 = valleys[v1_idx]
                    for v2_idx in range(v1_idx + 1, len(valleys) - 1):
                        v2 = valleys[v2_idx]
                        for v3_idx in range(v2_idx + 1, len(valleys)):
                            v3 = valleys[v3_idx]

                            # 检查是否符合头肩底形态
                            if (
                                abs(v1[1] - v3[1]) / v1[1] < 0.05
                                and v2[1] < v1[1] * 0.9  # 左右肩深度相近
                                and v2[1] < v3[1] * 0.9
                                and v2[0] - v1[0] > window // 4  # 头部明显低于两肩
                                and v3[0] - v2[0] > window // 4  # 确保谷值之间有足够距离
                            ):

                                # 检查颈线水平
                                neckline1 = max(window_prices[v1[0] : v2[0]])
                                neckline2 = max(window_prices[v2[0] : v3[0]])
                                if (
                                    abs(neckline1 - neckline2) / neckline1
                                    < 0.03
                                ):  # 颈线较为水平
                                    pattern.iloc[i] = 100

        return pattern

    @staticmethod
    def detect_support_resistance(
        df: pd.DataFrame, window: int = 20, price_threshold: float = 0.02
    ) -> Dict[str, List[float]]:
        """
        检测支撑位和压力位

        参数:
            window: 寻找局部极值的窗口大小
            price_threshold: 价格聚类的阈值（百分比）

        返回:
            包含支撑位和压力位的字典
        """
        support_levels = []
        resistance_levels = []
        prices = df['Close'].values

        # 寻找局部最小值作为潜在支撑位
        for i in range(window, len(prices) - window):
            price_window = prices[i - window : i + window]
            current_price = prices[i]

            # 判断是否为局部最小值
            if current_price == min(price_window):
                # 检查是否与已有支撑位接近
                if not any(
                    abs(level - current_price) / current_price
                    < price_threshold
                    for level in support_levels
                ):
                    support_levels.append(current_price)

        # 寻找局部最大值作为潜在压力位
        for i in range(window, len(prices) - window):
            price_window = prices[i - window : i + window]
            current_price = prices[i]

            # 判断是否为局部最大值
            if current_price == max(price_window):
                # 检查是否与已有压力位接近
                if not any(
                    abs(level - current_price) / current_price
                    < price_threshold
                    for level in resistance_levels
                ):
                    resistance_levels.append(current_price)

        # 排序并返回结果
        return {
            'support_levels': sorted(support_levels),
            'resistance_levels': sorted(resistance_levels),
        }

    @staticmethod
    def detect_trend_lines(
        df: pd.DataFrame, window: int = 20
    ) -> Dict[str, List[tuple]]:
        """
        检测趋势线

        返回:
            包含上升趋势线和下降趋势线的字典，每个趋势线由两个点的坐标组成
        """
        up_trends = []
        down_trends = []
        prices = df['Close'].values

        # 寻找局部最小值作为上升趋势线的支撑点
        valleys = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
                valleys.append((i, prices[i]))

        # 寻找局部最大值作为下降趋势线的阻力点
        peaks = []
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
                peaks.append((i, prices[i]))

        # 连接谷点形成潜在的上升趋势线
        for i in range(len(valleys) - 1):
            for j in range(i + 1, len(valleys)):
                v1, v2 = valleys[i], valleys[j]
                # 确保趋势线是向上的
                if v2[1] > v1[1]:
                    # 计算斜率
                    slope = (v2[1] - v1[1]) / (v2[0] - v1[0])
                    # 检查中间的点是否都在趋势线上方
                    valid_trend = True
                    for k in range(v1[0] + 1, v2[0]):
                        expected_price = v1[1] + slope * (k - v1[0])
                        if prices[k] < expected_price:
                            valid_trend = False
                            break
                    if valid_trend:
                        up_trends.append((v1, v2))

        # 连接峰点形成潜在的下降趋势线
        for i in range(len(peaks) - 1):
            for j in range(i + 1, len(peaks)):
                p1, p2 = peaks[i], peaks[j]
                # 确保趋势线是向下的
                if p2[1] < p1[1]:
                    # 计算斜率
                    slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                    # 检查中间的点是否都在趋势线下方
                    valid_trend = True
                    for k in range(p1[0] + 1, p2[0]):
                        expected_price = p1[1] + slope * (k - p1[0])
                        if prices[k] > expected_price:
                            valid_trend = False
                            break
                    if valid_trend:
                        down_trends.append((p1, p2))

        return {'up_trends': up_trends, 'down_trends': down_trends}

    @classmethod
    def detect_all_patterns(
        cls, df: pd.DataFrame, window: int = 20
    ) -> Dict[str, Union[pd.Series, Dict]]:
        """
        检测所有可能的形态

        返回:
            包含所有检测到的形态的字典
        """
        all_patterns = {}

        # 检测K线形态
        candlestick_patterns = cls.detect_candlestick_patterns(df)
        all_patterns['candlestick'] = candlestick_patterns

        # 检测价格形态
        price_patterns = cls.detect_price_patterns(df, window)
        all_patterns['price'] = price_patterns

        # 检测支撑压力位
        support_resistance = cls.detect_support_resistance(df, window)
        all_patterns['support_resistance'] = support_resistance

        # 检测趋势线
        trend_lines = cls.detect_trend_lines(df, window)
        all_patterns['trend_lines'] = trend_lines

        return all_patterns
