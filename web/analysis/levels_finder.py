import talib


class LevelsFinder:
    @staticmethod
    def find_key_levels(df, current_price):
        """平衡的关键价位计算"""
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values

        # 计算多个技术指标
        upper, middle, lower = talib.BBANDS(close, timeperiod=20)
        sar = talib.SAR(high, low)
        ma20 = talib.MA(close, timeperiod=20)
        ma50 = talib.MA(close, timeperiod=50)
        ma120 = talib.MA(close, timeperiod=120)

        # 计算多个时间周期的轴心点位
        def calculate_pivot_levels(h, l, c):
            pivot = (h + l + c) / 3
            r1 = 2 * pivot - l
            r2 = pivot + (h - l)
            r3 = r1 + (h - l)
            s1 = 2 * pivot - h
            s2 = pivot - (h - l)
            s3 = s1 - (h - l)
            return [r3, r2, r1, pivot, s1, s2, s3]

        # 计算多个周期的轴心点位
        pivot_levels_short = calculate_pivot_levels(
            high[-20], low[-20], close[-20]
        )
        pivot_levels_medium = calculate_pivot_levels(
            high[-50], low[-50], close[-50]
        )

        # 收集所有可能的价格水平
        resistance_levels = set(
            [
                float(upper[-1]),  # 布林上轨
                float(sar[-1]),  # SAR
                float(pivot_levels_short[0]),  # 短期R3
                float(pivot_levels_short[1]),  # 短期R2
                float(pivot_levels_short[2]),  # 短期R1
                float(pivot_levels_medium[0]),  # 中期R3
                float(pivot_levels_medium[1]),  # 中期R2
                float(pivot_levels_medium[2]),  # 中期R1
            ]
        )

        support_levels = set(
            [
                float(lower[-1]),  # 布林下轨
                float(ma20[-1]),  # MA20
                float(ma50[-1]),  # MA50
                float(ma120[-1]),  # MA120
                float(pivot_levels_short[4]),  # 短期S1
                float(pivot_levels_short[5]),  # 短期S2
                float(pivot_levels_short[6]),  # 短期S3
                float(pivot_levels_medium[4]),  # 中期S1
                float(pivot_levels_medium[5]),  # 中期S2
                float(pivot_levels_medium[6]),  # 中期S3
            ]
        )

        # 设置价格区间限制（放宽范围）
        min_gap = current_price * 0.01  # 降低最小间距到1%
        max_up = current_price * 1.06  # 增加上限到6%
        max_down = current_price * 0.94  # 增加下限到6%

        # 筛选有效价位（放宽条件）
        valid_resistances = sorted(
            [p for p in resistance_levels if current_price < p <= max_up]
        )

        valid_supports = sorted(
            [p for p in support_levels if max_down <= p < current_price],
            reverse=True,
        )

        # 去除过于接近的价位
        def filter_levels(levels, min_gap):
            result = []
            for level in levels:
                if not result or abs(level - result[-1]) >= min_gap:
                    result.append(level)
            return result

        resistances = filter_levels(valid_resistances, min_gap)
        supports = filter_levels(valid_supports, min_gap)

        # 补充价位（如果技术位不够）
        def generate_levels(base_price, count, is_resistance=True):
            levels = []
            steps = [0.01, 0.02, 0.03, 0.04, 0.05]  # 更多的步长选择

            for i in range(count):
                step = steps[min(i, len(steps) - 1)]
                if is_resistance:
                    new_level = base_price * (1 + step)
                    if new_level <= max_up:
                        levels.append(new_level)
                else:
                    new_level = base_price * (1 - step)
                    if new_level >= max_down:
                        levels.append(new_level)
            return levels

        # 确保至少有3个水平
        if len(resistances) < 3:
            base_price = resistances[-1] if resistances else current_price
            additional = generate_levels(
                base_price, 3 - len(resistances), True
            )
            resistances.extend(additional)

        if len(supports) < 3:
            base_price = supports[-1] if supports else current_price
            additional = generate_levels(base_price, 3 - len(supports), False)
            supports.extend(additional)

        # 格式化价格
        def format_price(price):
            if price >= 100:
                return round(price, 2)
            elif price >= 1:
                return round(price, 3)
            else:
                return round(price, 4)

        # 返回前3个最佳水平
        return {
            'resistances': [format_price(r) for r in resistances[:3]],
            'supports': [format_price(s) for s in supports[:3]],
        }

    @staticmethod
    def calculate_stop_loss(entry_price, direction='long', volatility=None):
        """改进的止损计算"""
        # 基础止损率
        base_risk = 0.02  # 2%基础风险

        # 根据波动率调整止损
        if volatility:
            # 如果波动率小于1%，收紧止损
            if volatility < 1:
                risk = base_risk * 0.8
            # 如果波动率大于2%，放宽止损
            elif volatility > 2:
                risk = base_risk * 1.2
            else:
                risk = base_risk
        else:
            risk = base_risk

        if direction == 'long':
            stop_loss = entry_price * (1 - risk)
        else:
            stop_loss = entry_price * (1 + risk)

        return round(stop_loss, 2)
