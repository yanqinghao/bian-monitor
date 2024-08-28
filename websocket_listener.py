import aiohttp
import asyncio
import json
from utils import format_timestamp, play_alert_sound


async def listen_to_stream(
    stream_url, proxy_url, alert_window, reconnect_delay=5, timeout=10
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
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if 'aggTrade' in stream_url:
                                event_time = format_timestamp(data.get('T'))
                                name = data.get('s')
                                price = data.get('p')

                                alert_window.update_data(
                                    name, event_time, price
                                )
                                play_alert_sound(name, data.get('p'))
                            else:
                                data = data.get('k')
                                event_time = format_timestamp(data.get('T'))
                                name = data.get('s')
                                price = f"high: {data.get('h')} low: {data.get('l')}"

                                alert_window.update_data(
                                    name, event_time, price
                                )
                                play_alert_sound(name, data.get('h'))
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            alert_window.show_error_message(
                                'WebSocket close',
                                f'WebSocket closed, reconnecting in {reconnect_delay} seconds...',
                            )
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            alert_window.show_error_message(
                                'WebSocket error',
                                f'WebSocket error, reconnecting in {reconnect_delay} seconds...',
                            )
                            break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            alert_window.show_error_message(
                'Connection error',
                f'Connection error: {e}, reconnecting in {reconnect_delay} seconds...',
            )
        except asyncio.CancelledError:
            alert_window.show_info_message(
                'listener cancelled', f'{stream_url} listener cancelled'
            )
            break
        except Exception as e:
            alert_window.show_error_message(
                'Unexpected error',
                f'Unexpected error: {e}, reconnecting in {reconnect_delay} seconds...',
            )

        # 确保在每次重连之前任务取消被正确处理
        try:
            await asyncio.sleep(reconnect_delay)
        except asyncio.CancelledError:
            alert_window.show_info_message(
                'listener cancelled', f'{stream_url} listener cancelled'
            )
            break
