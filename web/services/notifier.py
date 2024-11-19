import requests
import logging
from typing import Optional
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

        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def send_message(self, message: str) -> bool:
        """
        发送消息到Telegram群组

        Args:
            message (str): 要发送的消息内容

        Returns:
            bool: 发送是否成功
        """
        try:
            url = f'{self.api_base}/sendMessage'
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
            }

            response = requests.post(url, json=payload)
            if response.status_code == 200:
                self.logger.info('Telegram消息发送成功')
                return True
            else:
                self.logger.error(
                    f'发送失败: {response.status_code} - {response.text}'
                )
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
        risk_level: str,
        volume_data: Optional[dict] = None,
        reasons: Optional[list] = None,
        action_guide: Optional[str] = None,
    ) -> str:
        """
        格式化交易信号消息

        Args:
            symbol (str): 交易对
            signal_type (str): 信号类型
            current_price (float): 当前价格
            signal_score (float): 信号强度
            risk_level (str): 风险等级
            volume_data (dict, optional): 成交量数据
            reasons (list, optional): 触发原因
            action_guide (str, optional): 操作建议

        Returns:
            str: 格式化后的消息
        """
        # 信号类型映射
        signal_emoji = {
            'buy': '📈 买入',
            'strong_buy': '🔥🔥🔥 强力买入',
            'strong_sell': '❄️❄️❄️ 强力卖出',
        }

        # 风险等级映射
        risk_emoji = {'high': '⚠️ 高风险', 'medium': '⚡️ 中等风险', 'low': '✅ 低风险'}

        message = [
            f"<b>{'='*20} 交易信号 {'='*20}</b>",
            f'\n📊 交易对: <b>{symbol.upper()}</b>',
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f'💰 当前价格: {current_price:.8f}',
            f'📈 信号类型: {signal_emoji.get(signal_type, signal_type)}',
            f'💪 信号强度: {signal_score:.1f}/100',
            f'⚠️ 风险等级: {risk_emoji.get(risk_level, risk_level)}',
        ]

        # 添加成交量信息
        if volume_data:
            if 'ratio' in volume_data:
                message.append(f"📊 成交量比率: {volume_data['ratio']:.2f}")
            if 'pressure_ratio' in volume_data:
                message.append(f"⚖️ 买卖比: {volume_data['pressure_ratio']:.2f}")

        # 添加触发原因
        if reasons:
            reason_list = [f'- {reason}' for reason in reasons]
            message.append(f'\n📝 触发原因:\n' + '\n'.join(reason_list))

        # 添加操作建议
        if action_guide:
            message.append(f'\n💡 操作建议:\n{action_guide}')

        return '\n'.join(message)
