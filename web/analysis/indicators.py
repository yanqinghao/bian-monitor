import talib
import pandas as pd


class TechnicalIndicators:
    @staticmethod
    def calculate_indicators(df):
        """使用TA-Lib计算技术指标"""
        indicators = {}

        # MACD
        macd, signal, hist = talib.MACD(df['Close'])
        indicators['macd'] = {'macd': macd, 'signal': signal, 'hist': hist}

        # KDJ (使用TA-Lib的随机指标)
        k, d = talib.STOCH(
            df['High'],
            df['Low'],
            df['Close'],
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )
        j = 3 * k - 2 * d
        indicators['kdj'] = {'k': k, 'd': d, 'j': j}

        # MA均线
        ma_periods = [5, 10, 20, 60]
        mas = {}
        for period in ma_periods:
            mas[f'MA{period}'] = talib.MA(df['Close'], timeperiod=period)
        indicators['ma'] = mas

        # RSI
        rsi = talib.RSI(df['Close'], timeperiod=14)
        indicators['rsi'] = rsi

        return indicators

    @staticmethod
    def calculate_volatility_metrics(df):
        """计算波动率指标"""
        returns = df['Close'].pct_change()
        atr = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=14)

        return {
            'returns_volatility': returns.std() * 100,
            'atr': atr,
            'atr_percent': (atr / df['Close'].mean()) * 100,
        }


class AdvancedTechnicalIndicators:
    """高级技术指标类 - 包含扩展的技术指标"""

    @staticmethod
    def calculate_advanced_indicators(df):
        """计算进阶技术指标"""
        advanced_indicators = {}

        # 布林带
        upper, middle, lower = talib.BBANDS(
            df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2
        )
        advanced_indicators['bollinger'] = {
            'upper': upper,
            'middle': middle,
            'lower': lower,
        }

        # DMI/ADX
        adx = talib.ADX(df['High'], df['Low'], df['Close'], timeperiod=14)
        plus_di = talib.PLUS_DI(
            df['High'], df['Low'], df['Close'], timeperiod=14
        )
        minus_di = talib.MINUS_DI(
            df['High'], df['Low'], df['Close'], timeperiod=14
        )
        advanced_indicators['dmi'] = {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
        }

        # TRIX
        trix = talib.TRIX(df['Close'], timeperiod=30)
        advanced_indicators['trix'] = trix

        # OBV - 能量潮指标
        obv = talib.OBV(df['Close'], df['Volume'])
        advanced_indicators['obv'] = obv

        # CCI - 商品通道指数
        cci = talib.CCI(df['High'], df['Low'], df['Close'], timeperiod=14)
        advanced_indicators['cci'] = cci

        # 计算更多周期的RSI
        rsi_periods = [6, 21, 28]  # 额外的RSI周期
        rsi_dict = {}
        for period in rsi_periods:
            rsi_dict[f'RSI{period}'] = talib.RSI(
                df['Close'], timeperiod=period
            )
        advanced_indicators['additional_rsi'] = rsi_dict

        # 额外的移动平均线
        extra_ma_periods = [120, 250]  # 额外的均线周期
        extra_mas = {}
        for period in extra_ma_periods:
            extra_mas[f'MA{period}'] = talib.MA(df['Close'], timeperiod=period)
        advanced_indicators['additional_ma'] = extra_mas

        return advanced_indicators

    @staticmethod
    def calculate_advanced_volatility(df):
        """计算进阶波动率指标"""
        advanced_volatility = {}

        # 真实波动幅度区间
        advanced_volatility['tr'] = talib.TRANGE(
            df['High'], df['Low'], df['Close']
        )

        # 不同周期的ATR
        atr_periods = [5, 10, 21]
        for period in atr_periods:
            advanced_volatility[f'atr_{period}'] = talib.ATR(
                df['High'], df['Low'], df['Close'], timeperiod=period
            )

        # 价格波动性指标
        advanced_volatility['natr'] = talib.NATR(
            df['High'], df['Low'], df['Close']
        )

        return advanced_volatility

    @staticmethod
    def calculate_trend_strength(df):
        """计算趋势强度指标"""
        trend_metrics = {}

        # ADX - 趋势强度指标
        trend_metrics['adx'] = talib.ADX(
            df['High'], df['Low'], df['Close'], timeperiod=14
        )

        # 价格动量
        momentum_periods = [10, 21, 55]
        for period in momentum_periods:
            trend_metrics[f'momentum_{period}'] = talib.MOM(
                df['Close'], timeperiod=period
            )

        # 移动平均趋势
        ma20 = talib.MA(df['Close'], timeperiod=20)
        ma50 = talib.MA(df['Close'], timeperiod=50)

        # 计算MA趋势方向（1:上涨, -1:下跌, 0:盘整）
        trend_metrics['ma_trend'] = pd.Series(0, index=df.index)
        trend_metrics['ma_trend'][ma20 > ma20.shift(1)] = 1
        trend_metrics['ma_trend'][ma20 < ma20.shift(1)] = -1

        # 计算均线多空排列
        trend_metrics['ma_alignment'] = pd.Series(0, index=df.index)
        ma_alignment = ma20 > ma50
        trend_metrics['ma_alignment'] = ma_alignment.astype(int) * 2 - 1

        return trend_metrics
