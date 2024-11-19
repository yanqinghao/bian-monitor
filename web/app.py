import os
import json
from flask import (
    Response,
    Flask,
    send_from_directory,
    request,
    send_file,
    jsonify,
)
import requests
import csv
from datetime import datetime, timedelta
import tempfile
import zipfile
import io
import threading
from analysis.crypto_analyzer import CryptoAnalyzer
from services.monitor import MarketMonitor

app = Flask(__name__, static_folder='statics', static_url_path='')
app.config['JSON_AS_ASCII'] = False

# 创建全局的 MarketMonitor 实例
market_monitor = None


def start_market_monitor():
    """
    在单独的线程中启动市场监控
    """
    global market_monitor
    try:
        market_monitor = MarketMonitor()
        market_monitor.start_monitoring()
        print('\n市场监控已启动')
    except Exception as e:
        print(f'启动市场监控失败: {e}')


def initialize_monitor():
    """
    初始化并启动市场监控
    """
    monitor_thread = threading.Thread(target=start_market_monitor)
    monitor_thread.daemon = True  # 设置为守护线程，这样主程序退出时会自动关闭
    monitor_thread.start()


# 使用 with app.app_context() 在应用启动时初始化监控器
def init_app(app):
    with app.app_context():
        initialize_monitor()


# 添加一个停止监控的路由
@app.route('/stop_monitor', methods=['POST'])
def stop_monitor():
    """
    停止市场监控
    """
    global market_monitor
    if market_monitor:
        try:
            market_monitor.stop()
            market_monitor = None
            return jsonify({'status': 'success', 'message': '市场监控已停止'})
        except Exception as e:
            return (
                jsonify({'status': 'error', 'message': f'停止监控失败: {str(e)}'}),
                500,
            )
    return jsonify({'status': 'warning', 'message': '监控未启动'})


# 添加一个启动监控的路由
@app.route('/start_monitor', methods=['POST'])
def start_monitor():
    """
    启动市场监控
    """
    global market_monitor
    if not market_monitor:
        try:
            initialize_monitor()
            return jsonify({'status': 'success', 'message': '市场监控已启动'})
        except Exception as e:
            return (
                jsonify({'status': 'error', 'message': f'启动监控失败: {str(e)}'}),
                500,
            )
    return jsonify({'status': 'warning', 'message': '监控已在运行'})


# 添加一个获取监控状态的路由
@app.route('/monitor_status', methods=['GET'])
def monitor_status():
    """
    获取监控状态
    """
    global market_monitor
    is_running = bool(market_monitor and market_monitor.running.is_set())
    return jsonify(
        {
            'status': 'running' if is_running else 'stopped',
            'message': '监控正在运行' if is_running else '监控已停止',
        }
    )


# 原有的路由和配置保持不变
TIMEFRAMES = {
    '3d_1200': ('3d', 1200),
    '1d_365': ('1d', 365),
    '1d_180': ('1d', 180),
    '1d_90': ('1d', 90),
    '1d_30': ('1d', 30),
    '4h_7': ('4h', 7),
    '1h_3': ('1h', 3),
    '15m_1': ('15m', 1),
}

COMMON_SYMBOLS = [
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'DOGEUSDT',
    'BNBUSDT',
    'SUIUSDT',
    'RAYUSDT',
    'XRPUSDT',
    'LINKUSDT',
    'LTCUSDT',
    'BCHUSDT',
]

PROXY = os.environ.get('BINANCE_PROXY', None)
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


def create_csv_file(data, symbol, interval, days):
    filename = f"kline_data_{symbol}_{interval}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with tempfile.NamedTemporaryFile(
        mode='w', delete=False, newline='', suffix='.csv'
    ) as temp_file:
        writer = csv.writer(temp_file)
        writer.writerow(
            [
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
            ]
        )
        for kline in data:
            writer.writerow(kline[:-1])

    return temp_file.name, filename


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/analysis/<symbol>', methods=['GET'])
def analysis(symbol: str):
    try:
        symbol = symbol.upper()
        analyzer = CryptoAnalyzer(symbol)
        result = analyzer.analyze()
        return Response(
            json.dumps(result, ensure_ascii=False),
            mimetype='application/json',
            content_type='application/json; charset=utf-8',
        )
    except Exception as e:
        return str(e), 400


@app.route('/download', methods=['POST'])
def download():
    symbol = request.form['symbol'].upper()
    timeframes = request.form.getlist('timeframes')

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(
        zip_buffer, 'a', zipfile.ZIP_DEFLATED, False
    ) as zip_file:
        for timeframe in timeframes:
            interval, days = TIMEFRAMES[timeframe]
            try:
                data = get_kline_data(symbol, interval, days)
                temp_file_path, filename = create_csv_file(
                    data, symbol, interval, days
                )
                zip_file.write(temp_file_path, filename)
                os.unlink(temp_file_path)
            except Exception as e:
                return str(e), 400

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'kline_data_{symbol}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
    )


@app.route('/validate_symbol', methods=['POST'])
def validate_symbol():
    symbol = request.form['symbol'].upper()
    url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'

    response = requests.get(url, proxies=PROXIES)
    if response.status_code == 200:
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})


@app.route('/common_symbols')
def get_common_symbols():
    return jsonify(COMMON_SYMBOLS)


# 在应用启动时初始化监控
init_app(app)

if __name__ == '__main__':
    app.run(debug=False)  # 在生产环境中使用debug=False
