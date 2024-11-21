import talib
import pandas as pd
from typing import Dict, List, Union
from enum import Enum


class TrendType(Enum):
    BULLISH = '上涨'
    BEARISH = '下跌'
    CONSOLIDATION = '整理'


class PatternCategory:
    def __init__(self, name: str, trend_type: TrendType, reliability: int):
        """
        初始化形态分类
        reliability: 可靠度 1-5, 5为最可靠
        """
        self.name = name
        self.trend_type = trend_type
        self.reliability = reliability


class EnhancedPatternDetection:
    """K线形态识别类"""

    # 形态分类字典
    PATTERN_CATEGORIES = {
        # 单根K线形态
        'DOJI': PatternCategory('十字星', TrendType.CONSOLIDATION, 3),  # 犹豫不决
        'HAMMER': PatternCategory('锤子线', TrendType.BULLISH, 4),  # 看涨反转
        'SHOOTING_STAR': PatternCategory('流星', TrendType.BEARISH, 4),  # 看跌反转
        'SPINNING_TOP': PatternCategory(
            '陀螺', TrendType.CONSOLIDATION, 2
        ),  # 市场犹豫
        'MARUBOZU': PatternCategory('光头光脚', TrendType.BULLISH, 4),  # 强势趋势
        'DRAGONFLY_DOJI': PatternCategory(
            '蜻蜓十字', TrendType.BULLISH, 3
        ),  # 潜在底部
        'GRAVESTONE_DOJI': PatternCategory(
            '墓碑十字', TrendType.BEARISH, 3
        ),  # 潜在顶部
        # 两根K线形态
        'ENGULFING': PatternCategory('吞噬形态', TrendType.BULLISH, 5),  # 强势反转
        'HARAMI': PatternCategory('孕线', TrendType.CONSOLIDATION, 3),  # 趋势减弱
        'PIERCING': PatternCategory('穿刺线', TrendType.BULLISH, 4),  # 看涨反转
        'DARK_CLOUD_COVER': PatternCategory(
            '乌云盖顶', TrendType.BEARISH, 4
        ),  # 看跌反转
        'KICKING': PatternCategory('反冲形态', TrendType.BULLISH, 4),  # 强势反转
        # 三根K线形态
        'MORNING_STAR': PatternCategory('晨星', TrendType.BULLISH, 5),  # 强势底部反转
        'EVENING_STAR': PatternCategory('暮星', TrendType.BEARISH, 5),  # 强势顶部反转
        'THREE_WHITE_SOLDIERS': PatternCategory(
            '三白兵', TrendType.BULLISH, 5
        ),  # 强势上涨
        'THREE_BLACK_CROWS': PatternCategory(
            '三黑鸦', TrendType.BEARISH, 5
        ),  # 强势下跌
        'THREE_INSIDE': PatternCategory(
            '三内部', TrendType.CONSOLIDATION, 3
        ),  # 盘整
        'THREE_OUTSIDE': PatternCategory('三外部', TrendType.BULLISH, 4),  # 突破
        # 其他复杂形态
        'ABANDONED_BABY': PatternCategory('弃婴', TrendType.BULLISH, 4),  # 反转
        'BELT_HOLD': PatternCategory('捉腰带线', TrendType.BULLISH, 3),  # 潜在反转
        'BREAKAWAY': PatternCategory('脱离', TrendType.BULLISH, 4),  # 突破
        'CONCEALING_BABY_SWALLOW': PatternCategory(
            '藏婴吞没', TrendType.BULLISH, 3
        ),  # 潜在反转
        'COUNTERATTACK': PatternCategory(
            '反击线', TrendType.CONSOLIDATION, 3
        ),  # 趋势减弱
        'CLOSING_MARUBOZU': PatternCategory(
            '收盘光头光脚', TrendType.BULLISH, 4
        ),  # 强势
        'RICKSHAW_MAN': PatternCategory(
            '黄包车夫', TrendType.CONSOLIDATION, 2
        ),  # 犹豫
        # 经典技术形态
        'DOUBLE_BOTTOM': PatternCategory('双底', TrendType.BULLISH, 5),  # 强势反转
        'DOUBLE_TOP': PatternCategory('双顶', TrendType.BEARISH, 5),  # 强势反转
        'HEAD_AND_SHOULDERS': PatternCategory(
            '头肩顶', TrendType.BEARISH, 5
        ),  # 顶部反转
        'INVERSE_HEAD_AND_SHOULDERS': PatternCategory(
            '头肩底', TrendType.BULLISH, 5
        ),  # 底部反转
    }

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, Dict]:
        """
        检测所有talib支持的K线形态
        返回包含形态信号和分类信息的字典

        Args:
            df: 包含Open, High, Low, Close数据的DataFrame

        Returns:
            Dict: {
                pattern_name: {
                    'signal': pattern_signal_series,
                    'category': PatternCategory
                }
            }
        """
        patterns = {}

        # 获取OHLC数据
        open_price = df['Open']
        high_price = df['High']
        low_price = df['Low']
        close_price = df['Close']

        # 单根K线形态
        patterns['DOJI'] = {
            'signal': talib.CDLDOJI(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES['DOJI'],
        }

        patterns['HAMMER'] = {
            'signal': talib.CDLHAMMER(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES['HAMMER'],
        }

        patterns['SHOOTING_STAR'] = {
            'signal': talib.CDLSHOOTINGSTAR(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'SHOOTING_STAR'
            ],
        }

        patterns['SPINNING_TOP'] = {
            'signal': talib.CDLSPINNINGTOP(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'SPINNING_TOP'
            ],
        }

        patterns['MARUBOZU'] = {
            'signal': talib.CDLMARUBOZU(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'MARUBOZU'
            ],
        }

        patterns['DRAGONFLY_DOJI'] = {
            'signal': talib.CDLDRAGONFLYDOJI(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'DRAGONFLY_DOJI'
            ],
        }

        patterns['GRAVESTONE_DOJI'] = {
            'signal': talib.CDLGRAVESTONEDOJI(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'GRAVESTONE_DOJI'
            ],
        }

        # 两根K线形态
        patterns['ENGULFING'] = {
            'signal': talib.CDLENGULFING(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'ENGULFING'
            ],
        }

        patterns['HARAMI'] = {
            'signal': talib.CDLHARAMI(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES['HARAMI'],
        }

        patterns['PIERCING'] = {
            'signal': talib.CDLPIERCING(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'PIERCING'
            ],
        }

        patterns['DARK_CLOUD_COVER'] = {
            'signal': talib.CDLDARKCLOUDCOVER(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'DARK_CLOUD_COVER'
            ],
        }

        patterns['KICKING'] = {
            'signal': talib.CDLKICKING(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES['KICKING'],
        }

        # 三根K线形态
        patterns['MORNING_STAR'] = {
            'signal': talib.CDLMORNINGSTAR(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'MORNING_STAR'
            ],
        }

        patterns['EVENING_STAR'] = {
            'signal': talib.CDLEVENINGSTAR(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'EVENING_STAR'
            ],
        }

        patterns['THREE_WHITE_SOLDIERS'] = {
            'signal': talib.CDL3WHITESOLDIERS(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'THREE_WHITE_SOLDIERS'
            ],
        }

        patterns['THREE_BLACK_CROWS'] = {
            'signal': talib.CDL3BLACKCROWS(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'THREE_BLACK_CROWS'
            ],
        }

        patterns['THREE_INSIDE'] = {
            'signal': talib.CDL3INSIDE(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'THREE_INSIDE'
            ],
        }

        patterns['THREE_OUTSIDE'] = {
            'signal': talib.CDL3OUTSIDE(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'THREE_OUTSIDE'
            ],
        }

        # 其他复杂形态
        patterns['ABANDONED_BABY'] = {
            'signal': talib.CDLABANDONEDBABY(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'ABANDONED_BABY'
            ],
        }

        patterns['BELT_HOLD'] = {
            'signal': talib.CDLBELTHOLD(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'BELT_HOLD'
            ],
        }

        patterns['BREAKAWAY'] = {
            'signal': talib.CDLBREAKAWAY(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'BREAKAWAY'
            ],
        }

        patterns['CONCEALING_BABY_SWALLOW'] = {
            'signal': talib.CDLCONCEALBABYSWALL(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'CONCEALING_BABY_SWALLOW'
            ],
        }

        patterns['COUNTERATTACK'] = {
            'signal': talib.CDLCOUNTERATTACK(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'COUNTERATTACK'
            ],
        }

        patterns['CLOSING_MARUBOZU'] = {
            'signal': talib.CDLCLOSINGMARUBOZU(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'CLOSING_MARUBOZU'
            ],
        }

        patterns['RICKSHAW_MAN'] = {
            'signal': talib.CDLRICKSHAWMAN(
                open_price, high_price, low_price, close_price
            ),
            'category': EnhancedPatternDetection.PATTERN_CATEGORIES[
                'RICKSHAW_MAN'
            ],
        }

        # 添加更多talib支持的形态
        patterns['ADVANCE_BLOCK'] = {
            'signal': talib.CDLADVANCEBLOCK(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('推进块', TrendType.BEARISH, 3),
        }

        patterns['HANGING_MAN'] = {
            'signal': talib.CDLHANGINGMAN(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('上吊线', TrendType.BEARISH, 4),
        }

        patterns['INVERTED_HAMMER'] = {
            'signal': talib.CDLINVERTEDHAMMER(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('倒锤子线', TrendType.BULLISH, 4),
        }

        patterns['MATCHING_LOW'] = {
            'signal': talib.CDLMATCHINGLOW(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('相同低价', TrendType.BULLISH, 3),
        }

        patterns['MAT_HOLD'] = {
            'signal': talib.CDLMATHOLD(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('铺垫形态', TrendType.BULLISH, 4),
        }

        patterns['RISING_FALLING_THREE'] = {
            'signal': talib.CDLRISEFALL3METHODS(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('上升下降三法', TrendType.CONSOLIDATION, 4),
        }

        patterns['SEPARATING_LINES'] = {
            'signal': talib.CDLSEPARATINGLINES(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('分离线', TrendType.CONSOLIDATION, 3),
        }

        patterns['STICK_SANDWICH'] = {
            'signal': talib.CDLSTICKSANDWICH(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('条形三明治', TrendType.BULLISH, 3),
        }

        patterns['TAKURI'] = {
            'signal': talib.CDLTAKURI(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('探水竿', TrendType.BULLISH, 3),
        }

        patterns['TASUKI_GAP'] = {
            'signal': talib.CDLTASUKIGAP(
                open_price, high_price, low_price, close_price
            ),
            'category': PatternCategory('跨越暇缺', TrendType.CONSOLIDATION, 3),
        }

        return patterns

    @staticmethod
    def detect_price_patterns(
        df: pd.DataFrame, window: int = 20
    ) -> Dict[str, pd.Series]:
        """检测价格形态"""
        patterns = {}

        # 双底形态检测
        patterns[
            'DOUBLE_BOTTOM'
        ] = EnhancedPatternDetection._detect_double_bottom(df, window)

        # 双顶形态检测
        patterns['DOUBLE_TOP'] = EnhancedPatternDetection._detect_double_top(
            df, window
        )

        # 头肩顶形态检测
        patterns[
            'HEAD_AND_SHOULDERS'
        ] = EnhancedPatternDetection._detect_head_and_shoulders(df, window)

        # 头肩底形态检测
        patterns[
            'INVERSE_HEAD_AND_SHOULDERS'
        ] = EnhancedPatternDetection._detect_inverse_head_and_shoulders(
            df, window
        )

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
    def detect_classic_patterns(
        df: pd.DataFrame, window: int = 20
    ) -> Dict[str, pd.Series]:
        """
        检测经典技术形态
        复用原代码中的实现
        """
        patterns = {}

        # 双底形态
        patterns[
            'DOUBLE_BOTTOM'
        ] = EnhancedPatternDetection._detect_double_bottom(df, window)

        # 双顶形态
        patterns['DOUBLE_TOP'] = EnhancedPatternDetection._detect_double_top(
            df, window
        )

        # 头肩顶形态
        patterns[
            'HEAD_AND_SHOULDERS'
        ] = EnhancedPatternDetection._detect_head_and_shoulders(df, window)

        # 头肩底形态
        patterns[
            'INVERSE_HEAD_AND_SHOULDERS'
        ] = EnhancedPatternDetection._detect_inverse_head_and_shoulders(
            df, window
        )

        return patterns

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

    @staticmethod
    def analyze_pattern_trend(
        pattern_results: Dict[str, Dict]
    ) -> Dict[str, List]:
        """
        分析检测到的形态并按趋势类型归类
        """
        trend_analysis = {'bullish': [], 'bearish': [], 'consolidation': []}

        for pattern_name, pattern_data in pattern_results.items():
            # 获取非零信号的位置
            signals = pattern_data['signal']
            category = pattern_data['category']

            # 遍历每个信号
            for i in range(len(signals)):
                if signals[i] != 0:
                    pattern_info = {
                        'pattern': category.name,
                        'position': i,
                        'reliability': category.reliability,
                        'signal_value': signals[i],
                    }

                    # 根据趋势类型归类
                    if category.trend_type == TrendType.BULLISH:
                        trend_analysis['bullish'].append(pattern_info)
                    elif category.trend_type == TrendType.BEARISH:
                        trend_analysis['bearish'].append(pattern_info)
                    else:
                        trend_analysis['consolidation'].append(pattern_info)

        return trend_analysis

    @staticmethod
    def get_trend_strength(df: pd.DataFrame, window: int = 20) -> float:
        """
        计算当前趋势强度
        返回值在-1到1之间，正值表示上涨趋势，负值表示下跌趋势
        """
        # 使用收盘价计算趋势
        close_prices = df['Close'].values

        # 计算价格变化
        price_change = (
            close_prices[-1] - close_prices[-window]
        ) / close_prices[-window]

        # 计算波动率
        volatility = df['Close'].pct_change().std()

        # 综合考虑价格变化和波动率
        trend_strength = price_change / (volatility * (window**0.5))

        # 将结果限制在-1到1之间
        return max(min(trend_strength, 1), -1)

    @classmethod
    def detect_all_patterns(
        cls, df: pd.DataFrame, window: int = 20
    ) -> Dict[str, Union[Dict, float]]:
        """
        检测所有可能的形态并进行趋势分析
        """
        # 检测K线形态
        candlestick_patterns = cls.detect_candlestick_patterns(df)

        # 分析趋势
        trend_analysis = cls.analyze_pattern_trend(candlestick_patterns)

        # 计算趋势强度
        trend_strength = cls.get_trend_strength(df, window)

        # 整合所有结果
        return {
            'patterns': candlestick_patterns,
            'trend_analysis': trend_analysis,
            'trend_strength': trend_strength,
        }
