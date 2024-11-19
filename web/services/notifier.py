import requests
import logging
from typing import Optional, List, Dict
from datetime import datetime


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        """
        初始化Telegram通知服务

        Args:
            bot_token (str): Telegram机器人的API token
            chat_id (str): 目标群组/频道的ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = f'https://api.telegram.org/bot{bot_token}'
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def send_message(self, message: str) -> bool:
        try:
            url = f'{self.api_base}/sendMessage'
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                self.logger.info('Telegram消息发送成功')
                return True
            
            self.logger.error(f'发送失败: {response.status_code} - {response.text}')
            return False

        except Exception as e:
            self.logger.error(f'发送Telegram消息时出错: {e}')
            return False

    def format_signal_message(
        self,
        symbol: str,
        signal_type: str,
        current_price: float,
        signal_score: float,
        technical_score: float,
        volume_data: Optional[dict] = None,
        risk_level: Optional[str] = None,
        momentum: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        signal_emoji = {
            'sell': '📉 卖出',
            'buy': '📈 买入',
            'strong_buy': '🔥🔥🔥 强力买入',
            'strong_sell': '❄️❄️❄️ 强力卖出'
        }

        volume_color = '🔴' if volume_data and volume_data.get('ratio', 1) > 2 else '⚪️'
        pressure_color = '🔴' if volume_data and volume_data.get('pressure_ratio', 1) > 1.5 else (
            '🔵' if volume_data and volume_data.get('pressure_ratio', 1) < 0.7 else '⚪️'
        )

        message = [
            f"<b>{'='*20} 交易信号 {'='*20}</b>",
            f'\n📊 交易对: <b>{symbol.upper()}</b>',
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f'💰 当前价格: {current_price:.8f}',
            f'📈 信号类型: {signal_emoji.get(signal_type, signal_type)}',
            f'💪 信号强度: {signal_score:.1f}/100',
            f'📊 技术得分: {technical_score:.1f}'
        ]

        if volume_data:
            if 'ratio' in volume_data:
                message.append(f"📊 成交量比率: {volume_color} {volume_data['ratio']:.2f}")
            if 'pressure_ratio' in volume_data:
                message.append(f"⚖️ 买卖比: {pressure_color} {volume_data['pressure_ratio']:.2f}")

        if risk_level:
            risk_emoji = {
                'high': '⚠️ 高风险',
                'medium': '⚡️ 中等风险',
                'low': '✅ 低风险'
            }
            message.append(f"⚠️ 风险等级: {risk_emoji.get(risk_level, risk_level)}")

        if momentum:
            message.append(f"💫 动能: {momentum}")

        if reason:
            message.append(f"\n📝 触发原因: {reason}")

        # 根据风险级别添加风险提示
        if risk_level == 'high':
            message.append("\n⚠️ 风险提示: 建议谨慎操作，注意控制仓位")
        elif risk_level == 'medium' and volume_data and volume_data.get('ratio', 1) > 3:
            message.append("\n⚡️ 风险提示: 注意量能过度放大带来的回撤风险")

        return '\n'.join(message)
    
    def format_batch_signals(self, signals_data: List[Dict]) -> str:
        """Format multiple signals into one message"""
        message_parts = [f"<b>{'='*20} 市场信号汇总 {'='*20}</b>\n"]
        
        for data in signals_data:
            signal_emoji = {
                'sell': '📉 卖出',
                'buy': '📈 买入',
                'strong_buy': '🔥🔥🔥 强力买入',
                'strong_sell': '❄️❄️❄️ 强力卖出'
            }
            
            volume_data = data.get('volume_data', {})
            volume_color = '🔴' if volume_data.get('ratio', 1) > 2 else '⚪️'
            pressure_color = '🔴' if volume_data.get('pressure_ratio', 1) > 1.5 else (
                '🔵' if volume_data.get('pressure_ratio', 1) < 0.7 else '⚪️')
                
            signal_part = [
                f"\n<b>{data['symbol'].upper()}</b>",
                f"💰 价格: {data['price']:.4f}",
                f"📈 信号: {signal_emoji.get(data['signal_type'], data['signal_type'])}",
                f"💪 强度: {data['score']:.1f}",
                f"📊 技术: {data.get('technical_score', 0):.1f}",
                f"🔄 成交量: {volume_color}{volume_data.get('ratio', 1):.2f}",
                f"⚖️ 买卖比: {pressure_color}{volume_data.get('pressure_ratio', 1):.2f}",
                f"⚠️ 风险: {data.get('risk_level', 'medium')}",
                f"💡 原因: {data.get('reason', '技术面信号')}"
            ]
            
            message_parts.append('\n'.join(signal_part))
            message_parts.append('-' * 30)
        
        message_parts.append(f"\n⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}")
        return '\n'.join(message_parts)
    
    def send_batch_signals(self, signals_data: List[Dict]) -> bool:
        """Send all signals in one message"""
        if not signals_data:
            return True
            
        message = self.format_batch_signals(signals_data)
        return self.send_message(message)
