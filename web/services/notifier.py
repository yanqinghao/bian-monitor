import requests
import logging
from typing import List, Dict, Any
from datetime import datetime
import time


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
        self.alert_messages = []

    def send_message(self, message: str) -> bool:
        try:
            url = f'{self.api_base}/sendMessage'
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
            }

            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return True

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
        technical_scores: str,
        trend_alignment: str,
        volume_data: Dict[str, Any],
        risk_level: str = 'medium',
        reason: str = '',
    ) -> str:
        """格式化信号消息，支持多时间周期展示"""

        # 信号类型映射和emoji
        signal_map = {
            'strong_buy': '🔥 强力买入信号 🔥',
            'buy': '📈 买入信号',
            'sell': '📉 卖出信号',
            'strong_sell': '❄️ 强力卖出信号 ❄️',
        }

        # 风险等级映射
        risk_map = {'high': '⚠️ 高风险', 'medium': '⚡️ 中等风险', 'low': '✅ 低风险'}

        # 成交量和买卖压力指标
        volume_emoji = '🔴' if volume_data.get('ratio', 1) > 2 else '⚪️'
        pressure_emoji = (
            '🔴'
            if volume_data.get('pressure_ratio', 1) > 1.5
            else '🔵'
            if volume_data.get('pressure_ratio', 1) < 0.7
            else '⚪️'
        )

        # 构建消息
        message_parts = [
            f'<b>{signal_map.get(signal_type, "未知信号")}</b>',
            f'\n🎯 交易对: <b>{symbol.upper()}</b>',
            f'💰 当前价格: <code>{current_price:.8f}</code>',
            f'📊 信号强度: <code>{signal_score:.1f}/100</code>',
            # 技术得分（多时间周期）
            '\n📈 技术分析:',
            f'<code>{technical_scores}</code>',
            # 趋势一致性
            f'🎯 趋势分析: <code>{trend_alignment}</code>',
            # 成交量信息
            '\n📊 成交量分析:',
            f'{volume_emoji} 量比: <code>{volume_data["ratio"]:.2f}</code>',
            f'{pressure_emoji} 买卖比: <code>{volume_data["pressure_ratio"]:.2f}</code>',
            # 风险等级
            f'\n⚠️ 风险等级: <code>{risk_map.get(risk_level, "未知风险")}</code>',
        ]

        # 添加信号触发原因
        if reason:
            message_parts.append(f'\n📝 触发原因:\n<code>{reason}</code>')

        # 风险提示
        message_parts.extend(
            [
                '\n--------------------------------',
                '⚠️ 风险提示:',
                '• 该信号仅供参考，请勿盲目追单',
                '• 请严格控制仓位，做好止损',
                '• 高杠杆有爆仓风险，请谨慎操作',
            ]
        )

        return '\n'.join(message_parts)

    def format_batch_message(self, signals: list) -> str:
        """格式化批量信号消息"""
        if not signals:
            return ''

        message_parts = ['🔔 批量信号提醒 🔔\n']

        for signal in signals:
            signal_type = signal['signal_type']
            symbol = signal['symbol']
            price = signal['price']
            score = signal['score']

            # 信号类型emoji
            type_emoji = {
                'strong_buy': '🔥',
                'buy': '📈',
                'sell': '📉',
                'strong_sell': '❄️',
            }.get(signal_type, '🔍')

            # 添加单个信号概要
            signal_summary = [
                f'{type_emoji} {symbol.upper()}',
                f'价格: {price:.8f}',
                f'得分: {score:.1f}',
                f'风险: {signal.get("risk_level", "medium")}',
            ]

            message_parts.append(' | '.join(signal_summary))

        message_parts.append('\n查看详细信号请等待单独通知...')
        return '\n'.join(message_parts)

    def format_batch_signals(self, signals_data: List[Dict]) -> str:
        """Format multiple signals into one message"""
        message_parts = [f"<b>{'='*20} 市场信号汇总 {'='*20}</b>\n"]

        for data in signals_data:
            signal_emoji = {
                'sell': '📉 卖出',
                'buy': '📈 买入',
                'strong_buy': '🔥🔥🔥 强力买入',
                'strong_sell': '❄️❄️❄️ 强力卖出',
            }

            volume_data = data.get('volume_data', {})
            volume_color = '🔴' if volume_data.get('ratio', 1) > 2 else '⚪️'
            pressure_color = (
                '🔴'
                if volume_data.get('pressure_ratio', 1) > 1.5
                else (
                    '🔵' if volume_data.get('pressure_ratio', 1) < 0.7 else '⚪️'
                )
            )

            signal_part = [
                f"\n<b>{data['symbol'].upper()}</b>",
                f"💰 价格: {data['price']:.4f}",
                f"📈 信号: {signal_emoji.get(data['signal_type'], data['signal_type'])}",
                f"💪 强度: {data['score']:.1f}",
                f"📊 技术: {data.get('technical_score', 0):.1f}",
                f"🔄 成交量: {volume_color}{volume_data.get('ratio', 1):.2f}",
                f"⚖️ 买卖比: {pressure_color}{volume_data.get('pressure_ratio', 1):.2f}",
                f"⚠️ 风险: {data.get('risk_level', 'medium')}",
                f"💡 原因: {data.get('reason', '技术面信号')}",
            ]

            message_parts.append('\n'.join(signal_part))
            message_parts.append('-' * 30)

        message_parts.append(
            f"\n⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}"
        )
        return '\n'.join(message_parts)

    def send_batch_signals(self, signals: list) -> None:
        """发送批量信号通知"""
        try:
            # 先发送概要信息
            batch_message = self.format_batch_message(signals)
            if batch_message:
                self.send_message(batch_message)
                time.sleep(1)  # 等待1秒避免消息发送过快

            # 然后发送详细信号
            for signal in signals:
                detailed_message = self.format_signal_message(
                    symbol=signal['symbol'],
                    signal_type=signal['signal_type'],
                    current_price=signal['price'],
                    signal_score=signal['score'],
                    technical_scores=signal.get('technical_scores', ''),
                    trend_alignment=signal.get('trend_alignment', '未知'),
                    volume_data=signal['volume_data'],
                    risk_level=signal.get('risk_level', 'medium'),
                    reason=signal.get('reason', ''),
                )
                self.send_message(detailed_message)
                time.sleep(1)  # 消息间隔1秒

        except Exception as e:
            print(f'发送批量信号失败: {e}')

    def rev_alert_message(self, msgs):
        self.alert_messages.extend(msgs)

    def send_alert_message(self):
        if self.alert_messages:
            split_num = len(self.alert_messages) // 5 + 1
            for i in range(split_num):
                risk_warning = (
                    '\n⚠️ 风险提示:\n'
                    '• 异常波动可能带来剧烈价格变动\n'
                    '• 建议适当调整仓位和止损\n'
                    '• 请勿盲目追涨杀跌\n'
                    '• 确保资金安全和风险控制'
                )
                message = '告警信号汇总'
                for msg in self.alert_messages[i * 5 : (i + 1) * 5]:
                    message += '\n--------------------------------'
                    message += msg
                message += risk_warning
                self.send_message(message)
            self.alert_messages = []
