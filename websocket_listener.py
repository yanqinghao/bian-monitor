import aiohttp
import asyncio
import json
import traceback
from candlestick_chart import Candle
from utils import format_timestamp, play_alert_sound


async def listen_to_stream(
    stream_url,
    proxy_url,
    alert_window,
    reconnect_delay=5,
    timeout=10,
    is_candle=False,
):
    while True:
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.ws_connect(
                    stream_url, proxy=proxy_url
                ) as websocket:
                    async for msg in websocket:
                        if not is_candle:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if 'aggTrade' in stream_url:
                                    event_time = format_timestamp(
                                        data.get('T')
                                    )
                                    name = data.get('s')
                                    price = float(data.get('p'))
                                    history_price_currency = [
                                        i['price']
                                        for i in alert_window.history_price[
                                            name
                                        ]
                                    ]
                                    if len(history_price_currency) == 0:
                                        trend = '⛔'
                                        percent_change = 0
                                    else:
                                        avg_price = sum(
                                            history_price_currency
                                        ) / len(history_price_currency)
                                        percent_change = (
                                            (price - avg_price) / avg_price
                                        ) * 100
                                        if percent_change < 0:
                                            trend = '📉'
                                        else:
                                            trend = '📈'

                                    trend += f'{percent_change:.2f}%'
                                    alert_window.update_data(
                                        name, event_time, price, trend
                                    )
                                    play_alert_sound(name, data.get('p'))
                                else:
                                    event_time = format_timestamp(
                                        data.get('E')
                                    )
                                    data = data.get('k')
                                    name = data.get('s')
                                    price = f"h: {data.get('h')} l: {data.get('l')} o: {data.get('o')} c: {data.get('c')}"
                                    price_close = float(data.get('c'))
                                    history_price_currency = [
                                        i['price_close']
                                        for i in alert_window.history_price[
                                            name
                                        ]
                                    ]
                                    if len(history_price_currency) == 0:
                                        trend = '⛔'
                                        percent_change = 0
                                    else:
                                        avg_price = sum(
                                            history_price_currency
                                        ) / len(history_price_currency)
                                        percent_change = (
                                            (price_close - avg_price)
                                            / avg_price
                                        ) * 100
                                        if percent_change < 0:
                                            trend = '📉'
                                        else:
                                            trend = '📈'

                                    trend += f'{percent_change:.2f}%'
                                    alert_window.update_data(
                                        name,
                                        event_time,
                                        price,
                                        trend,
                                        price_close,
                                    )
                                    play_alert_sound(name, data.get('c'))
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                print(
                                    'WebSocket close',
                                    f'WebSocket closed, reconnecting in {reconnect_delay} seconds...',
                                )
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                print(
                                    'WebSocket error',
                                    f'WebSocket error, reconnecting in {reconnect_delay} seconds...',
                                )
                                break
                        else:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                data = data.get('k')
                                candle = Candle(
                                    open=data.get('o'),
                                    close=data.get('c'),
                                    high=data.get('h'),
                                    low=data.get('l'),
                                    volume=data.get('v'),
                                    timestamp=data.get('t'),
                                )
                                alert_window.update_candlestick_chart(candle)
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                print(
                                    'WebSocket close',
                                    f'WebSocket closed, reconnecting in {reconnect_delay} seconds...',
                                )
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                print(
                                    'WebSocket error',
                                    f'WebSocket error, reconnecting in {reconnect_delay} seconds...',
                                )
                                break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(
                'Connection error',
                f'Connection error: {e}, reconnecting in {reconnect_delay} seconds...',
            )
        except asyncio.CancelledError:
            print('listener cancelled', f'{stream_url} listener cancelled')
            break
        except Exception as e:
            print(
                'Unexpected error',
                f'Unexpected error: {e}, reconnecting in {reconnect_delay} seconds...',
            )
            print(traceback.format_exc())

        # 确保在每次重连之前任务取消被正确处理
        try:
            await asyncio.sleep(reconnect_delay)
        except asyncio.CancelledError:
            print('listener cancelled', f'{stream_url} listener cancelled')
            break
