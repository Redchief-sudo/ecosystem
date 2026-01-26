import logging
from typing import Optional

import requests

logger = logging.getLogger('telegram_notifier')

class TelegramNotifier:
    """Handles sending notifications via Telegram."""
    
    def __init__(self, config: dict):
        """
        Initialize the Telegram notifier.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        try:
            # Get Telegram config with defaults
            telegram_config = config.get('notifications', {}).get('telegram', {})
            self.enabled = telegram_config.get('enabled', False)
            self.bot_token = telegram_config.get('bot_token', '')
            self.chat_id = str(telegram_config.get('chat_id', ''))
            
            if not self.enabled:
                logger.info("Telegram notifications are disabled")
                return
                
            if not self.bot_token or not self.chat_id:
                logger.warning("Telegram bot token or chat ID not configured in config.yaml")
                self.enabled = False
                return
                
            logger.info("✅ Telegram notifier initialized")
            logger.debug(f"Bot token: {self.bot_token[:5]}... (length: {len(self.bot_token)})")
            logger.debug(f"Chat ID: {self.chat_id}")
            
        except Exception as e:
            logger.error(f"Error initializing Telegram notifier: {e}")
            self.enabled = False
    
    def send_message(self, message: str) -> bool:
        """
        Send a message to the configured Telegram chat.
        
        Args:
            message: The message to send
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
