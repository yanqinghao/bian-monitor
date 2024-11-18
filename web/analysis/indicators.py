import talib


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
