import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from scipy.stats import gaussian_kde
import warnings
import requests

warnings.filterwarnings('ignore')

# Global proxy settings
PROXY = os.environ.get('BINANCE_PROXY', 'http://10.33.58.241:1081')
PROXIES = {'http': PROXY, 'https': PROXY}


def get_kline_data(symbol, interval, days):
    url = 'https://api.binance.com/api/v3/klines'
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int(
        (datetime.now() - timedelta(days=days)).timestamp() * 1000
    )

    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000,
    }

    response = requests.get(url, params=params, proxies=PROXIES, timeout=30)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f'Error: {response.status_code} - {response.text}')


def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD指标

    Parameters:
    df : DataFrame with 'Close' prices
    fast : fast EMA period (default: 12)
    slow : slow EMA period (default: 26)
    signal : signal EMA period (default: 9)

    Returns:
    macd, signal_line, histogram
    """
    # 计算快线和慢线的EMA
    ema_fast = (
        df['Close'].ewm(span=fast, adjust=False, min_periods=fast).mean()
    )
    ema_slow = (
        df['Close'].ewm(span=slow, adjust=False, min_periods=slow).mean()
    )

    # 计算MACD线（快线-慢线）
    macd = ema_fast - ema_slow

    # 计算信号线
    signal_line = macd.ewm(
        span=signal, adjust=False, min_periods=signal
    ).mean()

    # 计算MACD柱状图
    histogram = macd - signal_line

    return macd, signal_line, histogram


def calculate_kdj(df, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    low_list = df['Low'].rolling(window=n).min()
    high_list = df['High'].rolling(window=n).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def calculate_rsi(df, periods=14):
    """计算RSI指标"""
    close_delta = df['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=False).mean()
    ma_down = down.ewm(com=periods - 1, adjust=False).mean()
    rsi = ma_up / (ma_up + ma_down) * 100
    return rsi


def calculate_ma(df, periods=[5, 10, 20, 60]):
    """计算多个周期的移动平均线"""
    mas = {}
    for period in periods:
        mas[f'MA{period}'] = df['Close'].rolling(window=period).mean()
    return mas


def analyze_ma_trend(mas):
    """分析均线趋势和排列"""
    current_mas = {k: v.iloc[-1] for k, v in mas.items()}
    sorted_mas = sorted(current_mas.items(), key=lambda x: x[1], reverse=True)

    # 判断多空排列
    if sorted_mas[0][0] == 'MA5' and sorted_mas[-1][0] == 'MA60':
        return '多头排列', '强势上涨'
    elif sorted_mas[-1][0] == 'MA5' and sorted_mas[0][0] == 'MA60':
        return '空头排列', '强势下跌'
    else:
        return '均线交织', '震荡整理'


def calculate_support_resistance(df, lookback=20):
    """计算支撑阻力位"""
    current_price = df['Close'].iloc[-1]

    # 使用多个方法计算可能的支撑阻力位
    levels = []

    # 1. 使用最近的高低点
    highs = df['High'].tail(lookback)
    lows = df['Low'].tail(lookback)

    # 2. 计算价格密集区
    try:
        # KDE方法
        all_prices = np.concatenate([highs, lows])
        kde = gaussian_kde(all_prices)
        price_range = np.linspace(min(all_prices), max(all_prices), 100)
        density = kde(price_range)

        # 找出局部最大值
        for i in range(1, len(density) - 1):
            if density[i] > density[i - 1] and density[i] > density[i + 1]:
                levels.append(price_range[i])
    except:
        # 如果KDE方法失败，使用其他方法
        pass

    # 3. 使用最近的高点和低点
    recent_highs = df['High'].nlargest(3).values
    recent_lows = df['Low'].nsmallest(3).values
    levels.extend(recent_highs)
    levels.extend(recent_lows)

    # 4. 使用移动平均线作为动态支撑阻力位
    ma_periods = [5, 10, 20, 60]
    for period in ma_periods:
        ma = df['Close'].rolling(window=period).mean().iloc[-1]
        levels.append(ma)

    # 5. 使用前期高点和低点的移动平均
    pivot_high = df['High'].rolling(window=5).max().iloc[-1]
    pivot_low = df['Low'].rolling(window=5).min().iloc[-1]
    levels.extend([pivot_high, pivot_low])

    # 移除重复值并排序
    levels = sorted(set(levels))

    # 根据当前价格分类支撑位和阻力位
    supports = [level for level in levels if level < current_price]
    resistances = [level for level in levels if level > current_price]

    # 如果没有检测到阻力位，生成一些预估的阻力位
    if not resistances:
        resistances = [
            current_price * 1.01,  # 1% 位置
            current_price * 1.02,  # 2% 位置
            current_price * 1.05,  # 5% 位置
        ]

    # 如果没有检测到支撑位，生成一些预估的支撑位
    if not supports:
        supports = [
            current_price * 0.99,  # -1% 位置
            current_price * 0.98,  # -2% 位置
            current_price * 0.95,  # -5% 位置
        ]

    return sorted(supports, reverse=True), sorted(resistances)


def analyze_volume_trend(df):
    """分析成交量趋势"""
    avg_vol = df['Volume'].rolling(window=20).mean()
    recent_vol = df['Volume'].tail(5).mean()

    price_change = df['Close'].pct_change()
    vol_change = df['Volume'].pct_change()

    # 量价关系分析
    price_vol_corr = price_change.corr(vol_change)

    # 计算量能级别
    volume_level = recent_vol / avg_vol.mean()
    volume_trend = (
        '强劲放量'
        if volume_level > 1.5
        else '温和放量'
        if volume_level > 1.1
        else '量能萎缩'
    )

    return {
        'volume_trend': volume_trend,
        'price_vol_correlation': '量价配合' if price_vol_corr > 0.5 else '量价背离',
        'avg_volume': avg_vol.iloc[-1],
        'recent_volume': recent_vol,
        'volume_level': volume_level,
    }


def detect_divergence(df, macd, price_periods=10):
    """检测MACD背离"""
    price_highs = []
    macd_highs = []
    price_lows = []
    macd_lows = []

    for i in range(-price_periods, -1):
        if (
            df['Close'].iloc[i] > df['Close'].iloc[i - 1]
            and df['Close'].iloc[i] > df['Close'].iloc[i + 1]
        ):
            price_highs.append(df['Close'].iloc[i])
            macd_highs.append(macd.iloc[i])

        if (
            df['Close'].iloc[i] < df['Close'].iloc[i - 1]
            and df['Close'].iloc[i] < df['Close'].iloc[i + 1]
        ):
            price_lows.append(df['Close'].iloc[i])
            macd_lows.append(macd.iloc[i])

    bullish_div = (
        len(price_lows) >= 2
        and len(macd_lows) >= 2
        and price_lows[-1] < price_lows[-2]
        and macd_lows[-1] > macd_lows[-2]
    )

    bearish_div = (
        len(price_highs) >= 2
        and len(macd_highs) >= 2
        and price_highs[-1] > price_highs[-2]
        and macd_highs[-1] < macd_highs[-2]
    )

    return bullish_div, bearish_div


def calculate_momentum(df):
    """计算动量指标"""
    momentum = {
        'price_momentum': df['Close'].pct_change(periods=5).iloc[-1] * 100,
        'volume_momentum': df['Volume'].pct_change(periods=5).iloc[-1] * 100,
    }
    return momentum


def generate_trade_signals(df, supports, resistances, macd, signal):
    """生成交易信号

    Parameters:
    -----------
    df : DataFrame - 价格数据
    supports : list - 支撑位列表
    resistances : list - 阻力位列表
    macd : Series - MACD值(DIF)
    signal : Series - Signal值(DEA)
    """
    current_price = df['Close'].iloc[-1]
    signals = []

    # MACD交叉信号
    macd_trend = None
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        macd_trend = 'GOLDEN_CROSS'  # 金叉
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        macd_trend = 'DEAD_CROSS'  # 死叉

    # 1. 支撑位信号
    for support in supports[:2]:
        # 价格接近支撑位
        if 0.98 <= current_price / support <= 1.02:
            signal_strength = (
                'Strong' if macd_trend == 'GOLDEN_CROSS' else 'Medium'
            )
            signals.append(
                {
                    'type': 'LONG',
                    'price': support,
                    'strength': signal_strength,
                    'reason': f'支撑位买入 {"+ MACD金叉" if macd_trend == "GOLDEN_CROSS" else ""}',
                }
            )

    # 2. 阻力位信号
    for resistance in resistances[:2]:
        # 价格接近阻力位
        if 0.98 <= current_price / resistance <= 1.02:
            signal_strength = (
                'Strong' if macd_trend == 'DEAD_CROSS' else 'Medium'
            )
            signals.append(
                {
                    'type': 'SHORT',
                    'price': resistance,
                    'strength': signal_strength,
                    'reason': f'阻力位卖出 {"+ MACD死叉" if macd_trend == "DEAD_CROSS" else ""}',
                }
            )

    # 3. MACD信号
    if macd_trend:
        if macd_trend == 'GOLDEN_CROSS':
            signals.append(
                {
                    'type': 'LONG',
                    'price': current_price,
                    'strength': 'Medium',
                    'reason': 'MACD金叉信号',
                }
            )
        else:
            signals.append(
                {
                    'type': 'SHORT',
                    'price': current_price,
                    'strength': 'Medium',
                    'reason': 'MACD死叉信号',
                }
            )

    return signals


def analyze_market(df):
    """主分析函数"""
    # try:
    # 1. 计算技术指标
    macd, signal, hist = calculate_macd(df)
    k, d, j = calculate_kdj(df)
    rsi = calculate_rsi(df)
    mas = calculate_ma(df)
    volume_analysis = analyze_volume_trend(df)
    ma_trend, trend_strength = analyze_ma_trend(mas)
    supports, resistances = calculate_support_resistance(df)
    bullish_div, bearish_div = detect_divergence(df, macd)
    momentum = calculate_momentum(df)

    current_price = df['Close'].iloc[-1]

    # 2. 生成分析报告
    print('\n=================== 市场分析报告 ===================')
    print(f'\n当前价格: {current_price:.4f}')

    # 2.1 整体趋势研判
    print('\n============== 整体趋势研判 ==============')
    print(f'中长期趋势: {trend_strength}')
    print(f'均线系统: {ma_trend}')
    print(f"价格动量: {momentum['price_momentum']:.2f}%")
    print(
        f"趋势延续性: {'高' if volume_analysis['price_vol_correlation'] == '量价配合' else '中等'}"
    )
    print(
        f"趋势阶段: {'前期' if abs(momentum['price_momentum']) < 10 else '中期' if abs(momentum['price_momentum']) < 20 else '后期'}"
    )

    # 2.2 技术指标分析
    print('\n============== 技术指标分析 ==============')
    print('MACD指标:')
    print(f'• DIF(MACD): {macd.iloc[-1]:.4f}')
    print(f'• DEA(信号): {signal.iloc[-1]:.4f}')
    print(f'• 柱状值: {hist.iloc[-1]:.4f}')
    print(
        f"• 背离情况: {'底背离-做多信号' if bullish_div else '顶背离-做空信号' if bearish_div else '无背离'}"
    )

    print('\nKDJ指标:')
    print(f'• K值: {k.iloc[-1]:.2f}')
    print(f'• D值: {d.iloc[-1]:.2f}')
    print(f'• J值: {j.iloc[-1]:.2f}')
    print(
        f"• 状态: {'超买' if k.iloc[-1] > 80 else '超卖' if k.iloc[-1] < 20 else '中性'}"
    )

    print('\n均线系统:')
    for ma_name, ma_values in mas.items():
        print(f'• {ma_name}: {ma_values.iloc[-1]:.4f}')

    print('\n成交量分析:')
    print(f"• 量能状态: {volume_analysis['volume_trend']}")
    print(f"• 量价关系: {volume_analysis['price_vol_correlation']}")
    print(f"• 量能级别: {volume_analysis['volume_level']:.2f}")

    # 2.3 重要价位分析
    print('\n============== 重要价位分析 ==============')
    print('支撑位:')
    for i, support in enumerate(supports[:3], 1):
        diff_pct = (current_price - support) / support * 100
        print(f'• S{i}: {support:.4f} (距今: {diff_pct:.2f}%)')

    print('\n阻力位:')
    for i, resistance in enumerate(resistances[:3], 1):
        diff_pct = (resistance - current_price) / current_price * 100
        print(f'• R{i}: {resistance:.4f} (距今: {diff_pct:.2f}%)')
    print('\n突破确认条件:')
    print(f'• 上破确认: 站稳 {resistances[0]:.4f} 且日线收盘上破')
    print(f'• 下破确认: 跌破 {supports[0]:.4f} 且日线收盘下破')

    # 2.4 操作建议
    print('\n============== 操作建议 ==============')
    # 生成交易信号
    signals = generate_trade_signals(df, supports, resistances, macd, signal)

    if signals:
        print('交易信号:')
        for s in signals:
            print(
                f"• {s['type']}: {s['price']:.4f} - {s['strength']} ({s['reason']})"
            )

    # 计算风险收益比
    if supports and resistances:
        risk = abs(current_price - supports[0])
        reward = abs(resistances[0] - current_price)
        risk_reward = reward / risk if risk > 0 else 0

        print(f'\n风险收益比: {risk_reward:.2f}')

        print('\n仓位管理建议:')
        if risk_reward >= 2:
            print('• 建议仓位: 40%')
            print('• 分批建仓: 20% + 10% + 10%')
        elif risk_reward >= 1.5:
            print('• 建议仓位: 30%')
            print('• 分批建仓: 15% + 10% + 5%')
        else:
            print('• 建议仓位: 20%')
            print('• 分批建仓: 10% + 5% + 5%')

    print('\n============== 现货/合约建议 ==============')
    print('现货策略:')
    if supports and resistances:
        print(f'• 网格区间: {supports[0]:.4f} - {resistances[0]:.4f}')
        print(
            f'• 建议档位: {min(int((resistances[0]-supports[0])/current_price*100), 8)}档'
        )

    print('\n合约策略:')
    print(
        f"• 开仓方向: {'多单' if trend_strength == '强势上涨' else '空单' if trend_strength == '强势下跌' else '观望'}"
    )
    if risk_reward > 0:
        print(f'• 建议杠杆: {min(5, int(10/risk_reward))}倍')
        print(f'• 止损位: {supports[0]:.4f}')
        print(f'• 止盈位: {resistances[0]:.4f}')

    print('\n============== 风险提示 ==============')
    volatility = df['Close'].pct_change().std() * np.sqrt(24)
    print(f'• 24h波动率: {volatility*100:.2f}%')

    risk_level = (
        '高风险' if volatility > 0.05 else '中等风险' if volatility > 0.03 else '低风险'
    )
    print(f'• 风险等级: {risk_level}')
    if volatility > 0.05:
        print('• 警示: 当前波动剧烈，建议谨慎操作，做好风险控制')
    elif volatility > 0.03:
        print('• 提示: 市场波动较大，建议降低仓位')

    if volume_analysis['volume_level'] > 1.5:
        print('• 量能提示: 交易量显著放大，注意价格变动风险')

    print('\n============== 趋势研判 ==============')
    # 计算趋势强度指标
    trend_score = 0

    # 基于MACD
    if hist[-1] > 0 and hist[-2] > 0:
        trend_score += 1
    if macd[-1] > signal[-1]:
        trend_score += 1
    # 基于KDJ
    if k[-1] > d[-1]:
        trend_score += 1
    if j[-1] > 50:
        trend_score += 1
    # 基于RSI
    if rsi.iloc[-1] > 50:
        trend_score += 1

    # 基于均线
    if ma_trend[0] == '多头排列':
        trend_score += 2
    elif ma_trend[0] == '空头排列':
        trend_score -= 2

    # 基于成交量
    if volume_analysis['price_vol_correlation'] == '量价配合':
        trend_score += 1

    print(f'趋势强度得分: {trend_score}/7')
    print('趋势评级:', end=' ')
    if trend_score >= 5:
        print('强势上涨趋势')
    elif trend_score <= -5:
        print('强势下跌趋势')
    elif trend_score >= 3:
        print('温和上涨趋势')
    elif trend_score <= -3:
        print('温和下跌趋势')
    else:
        print('震荡整理')

    print('\n============== 短期操作建议 ==============')
    if trend_score >= 5:
        print('• 操作建议: 可积极做多')
        print(f'• 建议买入区间: {supports[0]:.4f} - {current_price:.4f}')
        print('• 仓位控制: 可采用高仓位(40%-60%)')
    elif trend_score >= 3:
        print('• 操作建议: 谨慎做多')
        print(f'• 建议买入区间: {supports[0]:.4f} - {supports[1]:.4f}')
        print('• 仓位控制: 建议中等仓位(20%-40%)')
    elif trend_score <= -5:
        print('• 操作建议: 可考虑做空')
        print(f'• 建议卖出区间: {current_price:.4f} - {resistances[0]:.4f}')
        print('• 仓位控制: 注意控制风险，建议低仓位(20%以下)')
    else:
        print('• 操作建议: 观望为主')
        print('• 建议等待更明确的市场信号')
        print('• 仓位控制: 建议以现货网格交易为主')

    print('\n============== 关键价位提醒 ==============')
    print('上方关注:')
    for i, resistance in enumerate(resistances[:3], 1):
        print(f'• R{i}: {resistance:.4f} (突破后目标: {resistance*1.02:.4f})')

    print('\n下方关注:')
    for i, support in enumerate(supports[:3], 1):
        print(f'• S{i}: {support:.4f} (跌破后风险: {support*0.98:.4f})')

    print('\n============== 总结建议 ==============')
    summary = []
    # 基于趋势
    if trend_score >= 3:
        summary.append('趋势向好，可择机做多')
    elif trend_score <= -3:
        summary.append('趋势走弱，注意风险')
    else:
        summary.append('趋势不明，以观望为主')

    # 基于量能
    if volume_analysis['volume_level'] > 1.2:
        summary.append('量能充足，可适当参与')
    else:
        summary.append('量能不足，建议谨慎')

    # 基于技术指标
    if bullish_div:
        summary.append('MACD底背离，可关注反弹机会')
    elif bearish_div:
        summary.append('MACD顶背离，注意回调风险')

    # 打印总结建议
    print('要点提示:')
    for i, point in enumerate(summary, 1):
        print(f'{i}. {point}')

    print('\n风险提示: 以上分析仅供参考，不构成投资建议，请根据自身情况作出判断')

    # except Exception as e:
    #     print(f"分析过程中出现错误: {str(e)}")


def main():
    """主函数"""
    # try:
    # # 建议获取15天的数据 1h 30天 4h 3个月的数据 1d 5天的数据 15m

    # days = 14
    # hours_needed = days * 24
    # 读取数据
    data = get_kline_data('BTCUSDT', '15m', 5)

    # Open time,Open,High,Low,Close,Volume,Close time,Quote asset volume,Number of trades,Taker buy base asset volume,Taker buy quote asset volume
    df = pd.DataFrame(
        data,
        columns=[
            'Open time',
            'Open',
            'High',
            'Low',
            'Close',
            'Volume',
            'Close time',
            'Quote asset volume',
            'Number of trades',
            'Taker buy base asset volume',
            'Taker buy quote asset volume',
            'ignore',
        ],
    )
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # 确保数据包含所需的列
    required_columns = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError('数据文件缺少必要的列')

    # 处理时间戳
    df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
    df.set_index('Open time', inplace=True)

    # 运行市场分析
    analyze_market(df)

    # except Exception as e:
    #     print(f"程序运行错误: {str(e)}")


if __name__ == '__main__':
    main()
