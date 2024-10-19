import os
from flask import Flask, send_from_directory, request, send_file, jsonify
import requests
import csv
from datetime import datetime, timedelta
import tempfile
import zipfile
import io

app = Flask(__name__, static_folder='statics', static_url_path='')

TIMEFRAMES = {
    '1d_30': ('1d', 30),
    '4h_7': ('4h', 7),
    '1h_3': ('1h', 3),
    '15m_1': ('15m', 1)
}

COMMON_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT', 'XRPUSDT', 'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'XLMUSDT']

# Global proxy settings
PROXY = os.environ.get('BINANCE_PROXY', None)
PROXIES = {'http': PROXY, 'https': PROXY}

def get_kline_data(symbol, interval, days):
    url = 'https://api.binance.com/api/v3/klines'
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

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
        raise Exception(f"Error: {response.status_code} - {response.text}")

def create_csv_file(data, symbol, interval, days):
    filename = f"kline_data_{symbol}_{interval}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv') as temp_file:
        writer = csv.writer(temp_file)
        writer.writerow([
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close time', 'Quote asset volume', 'Number of trades',
            'Taker buy base asset volume', 'Taker buy quote asset volume',
        ])
        for kline in data:
            writer.writerow(kline[:-1])
    
    return temp_file.name, filename

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/download', methods=['POST'])
def download():
    symbol = request.form['symbol'].upper()
    timeframes = request.form.getlist('timeframes')

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for timeframe in timeframes:
            interval, days = TIMEFRAMES[timeframe]
            try:
                data = get_kline_data(symbol, interval, days)
                temp_file_path, filename = create_csv_file(data, symbol, interval, days)
                zip_file.write(temp_file_path, filename)
                os.unlink(temp_file_path)
            except Exception as e:
                return str(e), 400

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'kline_data_{symbol}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    )

@app.route('/validate_symbol', methods=['POST'])
def validate_symbol():
    symbol = request.form['symbol'].upper()
    url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
    
    response = requests.get(url, proxies=PROXIES)
    if response.status_code == 200:
        return jsonify({"valid": True})
    else:
        return jsonify({"valid": False})

@app.route('/common_symbols')
def get_common_symbols():
    return jsonify(COMMON_SYMBOLS)

if __name__ == '__main__':
    app.run(debug=True)