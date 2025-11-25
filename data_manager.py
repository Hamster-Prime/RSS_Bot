import json
import os
import logging
from typing import Dict, Optional, Any
import feedparser

logger = logging.getLogger(__name__)

subscriptions_data: Dict[str, Dict[str, Any]] = {}


def get_feed_title(feed_url: str) -> Optional[str]:
    try:
        feed = feedparser.parse(feed_url)
        if feed.feed and feed.feed.title:
            return feed.feed.title
        logger.warning(f"无法获取订阅源的标题: {feed_url}")
    except Exception as e:
        logger.error(f"获取订阅源 {feed_url} 标题时出错: {e}")
    return None


def _ensure_feed_data_structure(feed_data: Dict[str, Any], feed_url: str) -> None:
    if "keywords" not in feed_data:
        feed_data["keywords"] = []
    if "last_entry_id" not in feed_data:
        feed_data["last_entry_id"] = None
    if "title" not in feed_data:
        feed_data["title"] = get_feed_title(feed_url) or "未知标题"


def _ensure_user_data_structure(user_config: Dict[str, Any]) -> Dict[str, Any]:
    if "rss_feeds" not in user_config:
        user_config["rss_feeds"] = {}
    else:
        for feed_url, feed_data in user_config["rss_feeds"].items():
            _ensure_feed_data_structure(feed_data, feed_url)
    
    if "custom_footer" not in user_config:
        user_config["custom_footer"] = None
    if "link_preview_enabled" not in user_config:
        user_config["link_preview_enabled"] = True
    
    return user_config


def load_subscriptions(data_file: str) -> Dict[str, Dict[str, Any]]:
    global subscriptions_data
    
    if not os.path.exists(data_file):
        logger.info(f"未找到 {data_file}。初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        subscriptions_data = {}
        for chat_id_str, user_config in loaded_data.items():
            chat_id = str(chat_id_str)
            subscriptions_data[chat_id] = _ensure_user_data_structure(user_config.copy())

        logger.info(f"订阅已成功从 {data_file} 加载")
    except json.JSONDecodeError as e:
        logger.error(f"解码 {data_file} 出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
    except Exception as e:
        logger.error(f"从 {data_file} 加载订阅出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
    
    return subscriptions_data


def save_subscriptions(data_file: str) -> None:
    global subscriptions_data
    
    try:
        data_dir = os.path.dirname(data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(subscriptions_data, f, indent=4, ensure_ascii=False)
        logger.debug(f"订阅已成功保存到 {data_file}")
    except Exception as e:
        logger.error(f"保存订阅到 {data_file} 时出错: {e}")


def get_subscriptions() -> Dict[str, Dict[str, Any]]:
    return subscriptions_data

