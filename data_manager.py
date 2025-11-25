import json
import os
import logging
from typing import Dict, Optional
import feedparser

logger = logging.getLogger(__name__)

subscriptions_data: Dict[str, dict] = {}


def get_feed_title(feed_url: str) -> Optional[str]:
    try:
        feed = feedparser.parse(feed_url)
        if feed.feed and feed.feed.title:
            return feed.feed.title
        logger.warning(f"无法获取订阅源的标题: {feed_url}")
    except Exception as e:
        logger.error(f"获取订阅源 {feed_url} 标题时出错: {e}")
    return None


def load_subscriptions(data_file: str) -> Dict[str, dict]:
    global subscriptions_data
    if not os.path.exists(data_file):
        logger.info(f"未找到 {data_file}。初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            for chat_id_str, user_config in loaded_data.items():
                chat_id = str(chat_id_str)
                if chat_id not in subscriptions_data:
                    subscriptions_data[chat_id] = {}

                if "rss_feeds" not in user_config:
                    subscriptions_data[chat_id]["rss_feeds"] = {}
                else:
                    subscriptions_data[chat_id]["rss_feeds"] = user_config["rss_feeds"]
                    for feed_url, feed_data in user_config.get("rss_feeds", {}).items():
                        if "keywords" not in feed_data:
                            feed_data["keywords"] = []
                        if "last_entry_id" not in feed_data:
                            feed_data["last_entry_id"] = None
                        if "title" not in feed_data:
                            feed_data["title"] = get_feed_title(feed_url) or "未知标题"
                
                subscriptions_data[chat_id]["custom_footer"] = user_config.get("custom_footer", None)
                subscriptions_data[chat_id]["link_preview_enabled"] = user_config.get("link_preview_enabled", True)

        logger.info(f"订阅已成功从 {data_file} 加载")
    except json.JSONDecodeError:
        logger.error(f"解码 {data_file} 出错。初始化为空订阅。")
        subscriptions_data = {}
    except Exception as e:
        logger.error(f"从 {data_file} 加载订阅出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
    return subscriptions_data


def save_subscriptions(data_file: str) -> None:
    global subscriptions_data
    try:
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(subscriptions_data, f, indent=4, ensure_ascii=False)
        logger.debug(f"订阅已成功保存到 {data_file}")
    except Exception as e:
        logger.error(f"保存订阅到 {data_file} 时出错: {e}")


def get_subscriptions() -> Dict[str, dict]:
    return subscriptions_data

