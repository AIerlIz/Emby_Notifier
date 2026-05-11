#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import os
import json
import requests
from typing import Dict, Any, Optional
from enum import Enum
import log


class TelegramAPIMethod(Enum):
    """Telegram Bot API 方法枚举"""
    SEND_MESSAGE = "sendMessage"
    SEND_PHOTO = "sendPhoto"
    GET_ME = "getMe"
    GET_CHAT = "getChat"


class TelegramBotConfig:
    """Telegram Bot 配置管理"""
    
    REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
    
    def __init__(self):
        self.bot_token = os.getenv("TG_BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")
        self._validate_config()
    
    def _validate_config(self):
        """验证必需的环境变量"""
        if not self.bot_token:
            raise ValueError("Environment variable 'TG_BOT_TOKEN' is not set")
        if not self.chat_id:
            raise ValueError("Environment variable 'TG_CHAT_ID' is not set")
    
    @property
    def api_url(self) -> str:
        """获取 Telegram API 基础 URL"""
        return f"https://api.telegram.org/bot{self.bot_token}/"


class TelegramBotException(Exception):
    """Telegram Bot 异常基类"""
    pass


class TelegramBotConnectionError(TelegramBotException):
    """连接错误"""
    pass


class TelegramBotAPIError(TelegramBotException):
    """API 返回错误"""
    pass


class TelegramBot:
    """Telegram Bot 客户端"""
    
    def __init__(self, config: Optional[TelegramBotConfig] = None):
        """
        初始化 Telegram Bot 客户端
        
        Args:
            config: TelegramBotConfig 实例，如果为 None 则自动创建
        """
        self.config = config or TelegramBotConfig()
    
    def _make_request(
        self,
        method: TelegramAPIMethod,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送 Telegram API 请求
        
        Args:
            method: API 方法
            payload: 请求负载
            
        Returns:
            API 响应数据
            
        Raises:
            TelegramBotConnectionError: 网络连接错误
            TelegramBotAPIError: API 返回错误
        """
        payload["method"] = method.value
        
        # 记录调试日志（脱敏处理）
        log.logger.debug(log.SensitiveData(json.dumps(payload, ensure_ascii=False)))
        
        try:
            response = requests.post(
                self.config.api_url,
                json=payload,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            error_msg = f"Telegram API request timeout: {e}"
            log.logger.error(error_msg)
            raise TelegramBotConnectionError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Telegram API connection failed: {e}"
            log.logger.error(error_msg)
            raise TelegramBotConnectionError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Telegram API request failed: {e}"
            log.logger.error(json.dumps(payload, ensure_ascii=False))
            log.logger.error(response.text if 'response' in locals() else str(e))
            raise TelegramBotAPIError(error_msg) from e
        
        try:
            result = response.json()
            if not result.get("ok", False):
                error_description = result.get("description", "Unknown error")
                error_msg = f"Telegram API error: {error_description}"
                log.logger.error(error_msg)
                raise TelegramBotAPIError(error_msg)
            return result.get("result", {})
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse Telegram API response: {e}"
            log.logger.error(error_msg)
            raise TelegramBotAPIError(error_msg) from e
    
    def send_message(self, text: str) -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            text: 消息内容
            
        Returns:
            API 响应数据
        """
        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        return self._make_request(TelegramAPIMethod.SEND_MESSAGE, payload)
    
    def send_photo(self, caption: str, photo: str) -> Dict[str, Any]:
        """
        发送图片消息
        
        Args:
            caption: 图片标题
            photo: 图片 URL 或 file_id
            
        Returns:
            API 响应数据
        """
        payload = {
            "chat_id": self.config.chat_id,
            "photo": photo,
            "caption": caption,
            "parse_mode": "Markdown",
        }
        return self._make_request(TelegramAPIMethod.SEND_PHOTO, payload)
    
    def bot_authorization(self) -> str:
        """
        验证 Bot 授权
        
        Returns:
            Bot 用户名
            
        Raises:
            TelegramBotConnectionError: 连接错误
            TelegramBotAPIError: API 错误
        """
        try:
            response = requests.get(
                self.config.api_url + TelegramAPIMethod.GET_ME.value,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("ok", False):
                raise TelegramBotAPIError("Bot authorization failed")
            
            bot_username = result["result"]["username"]
            log.logger.info(f"Telegram bot authorization successful. Current bot: {bot_username}")
            return bot_username
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Telegram bot authorization failed. Check network connection: {e}"
            log.logger.error(error_msg)
            raise TelegramBotConnectionError(error_msg) from e
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = f"Telegram bot authorization failed. Invalid response: {e}"
            log.logger.error(error_msg)
            raise TelegramBotAPIError(error_msg) from e
        except Exception as e:
            error_msg = f"Telegram bot authorization failed. Error: {e}"
            log.logger.error(error_msg)
            raise TelegramBotAPIError(error_msg) from e
    
    def get_chat_info(self) -> Dict[str, Any]:
        """
        获取聊天信息
        
        Returns:
            聊天信息字典，包含 type, username/title 等字段
            
        Raises:
            TelegramBotConnectionError: 连接错误
            TelegramBotAPIError: API 错误
        """
        payload = {"chat_id": self.config.chat_id}
        
        try:
            result = self._make_request(TelegramAPIMethod.GET_CHAT, payload)
            chat_type = result.get("type")
            
            if chat_type == "private":
                chat_name = result.get("username") or result.get("first_name", "Unknown")
            else:
                chat_name = result.get("title", "Unknown")
            
            log.logger.info(f"Telegram getChat successful. Chat: [{chat_name}], type: {chat_type}")
            return result
        except TelegramBotException:
            raise
        except Exception as e:
            error_msg = f"Telegram getChat failed. Error: {e}"
            log.logger.error(error_msg)
            raise TelegramBotAPIError(error_msg) from e


# 模块级别的全局实例（保持向后兼容性）
_bot_instance: Optional[TelegramBot] = None


def _get_bot() -> TelegramBot:
    """获取全局 Bot 实例"""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance


def send_message(text: str) -> Dict[str, Any]:
    """发送文本消息（保持向后兼容）"""
    return _get_bot().send_message(text)


def send_photo(caption: str, photo: str) -> Dict[str, Any]:
    """发送图片消息（保持向后兼容）"""
    return _get_bot().send_photo(caption, photo)


def bot_authorization() -> str:
    """验证 Bot 授权（保持向后兼容）"""
    return _get_bot().bot_authorization()


def get_chat() -> Dict[str, Any]:
    """获取聊天信息（保持向后兼容）"""
    return _get_bot().get_chat_info()
