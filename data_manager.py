import json
import logging
import os
from typing import Any, Dict, Optional

import feedparser

logger = logging.getLogger(__name__)

subscriptions_data: Dict[str, Dict[str, Any]] = {}


def get_feed_title(feed_url: str) -> Optional[str]:
    try:
        feed = feedparser.parse(feed_url)
        if feed.feed and feed.feed.title:
            return feed.feed.title
        logger.warning(f"无法获取订阅源标题: {feed_url}")
    except Exception as e:
        logger.error(f"获取订阅源 {feed_url} 标题时出错: {e}")
    return None


def _ensure_feed_data_structure(feed_data: Any, feed_url: str) -> Dict[str, Any]:
    normalized_feed_data = dict(feed_data) if isinstance(feed_data, dict) else {}

    raw_keywords = normalized_feed_data.get("keywords", [])
    if not isinstance(raw_keywords, list):
        raw_keywords = []

    normalized_feed_data["keywords"] = [
        str(keyword).strip()
        for keyword in raw_keywords
        if str(keyword).strip()
    ]

    if "last_entry_id" not in normalized_feed_data:
        normalized_feed_data["last_entry_id"] = None
    elif normalized_feed_data["last_entry_id"] is not None:
        normalized_feed_data["last_entry_id"] = str(normalized_feed_data["last_entry_id"])

    if "title" not in normalized_feed_data or not normalized_feed_data["title"]:
        normalized_feed_data["title"] = get_feed_title(feed_url) or "未知标题"
    else:
        normalized_feed_data["title"] = str(normalized_feed_data["title"])

    return normalized_feed_data


def _normalize_preview_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False

    return bool(value) if value is not None else True


def _ensure_user_data_structure(user_config: Any) -> Dict[str, Any]:
    normalized_user_config = dict(user_config) if isinstance(user_config, dict) else {}
    rss_feeds = normalized_user_config.get("rss_feeds", {})

    if not isinstance(rss_feeds, dict):
        logger.warning("检测到无效的 rss_feeds 结构，已重置为空字典。")
        rss_feeds = {}

    normalized_feeds = {}
    for feed_url, feed_data in rss_feeds.items():
        if not isinstance(feed_url, str):
            logger.warning("检测到非字符串订阅地址，已跳过。")
            continue
        normalized_feeds[feed_url] = _ensure_feed_data_structure(feed_data, feed_url)

    normalized_user_config["rss_feeds"] = normalized_feeds

    custom_footer = normalized_user_config.get("custom_footer")
    if custom_footer is not None and not isinstance(custom_footer, str):
        custom_footer = str(custom_footer)
    normalized_user_config["custom_footer"] = custom_footer

    normalized_user_config["link_preview_enabled"] = _normalize_preview_flag(
        normalized_user_config.get("link_preview_enabled", True)
    )

    return normalized_user_config


def load_subscriptions(data_file: str) -> Dict[str, Dict[str, Any]]:
    global subscriptions_data

    if not os.path.exists(data_file):
        logger.info(f"未找到 {data_file}，初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data

    try:
        with open(data_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"解析 {data_file} 出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data
    except Exception as e:
        logger.error(f"从 {data_file} 加载订阅时出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data

    if not isinstance(loaded_data, dict):
        logger.error(f"{data_file} 的顶层结构不是对象，初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data

    normalized_data = {}
    for chat_id_str, user_config in loaded_data.items():
        chat_id = str(chat_id_str)
        if not isinstance(user_config, dict):
            logger.warning("聊天 %s 的订阅数据结构无效，已跳过。", chat_id)
            continue
        normalized_data[chat_id] = _ensure_user_data_structure(user_config)

    subscriptions_data = normalized_data
    logger.info(f"订阅已成功从 {data_file} 加载")
    return subscriptions_data


def save_subscriptions(data_file: str) -> None:
    global subscriptions_data

    temp_file = f"{data_file}.tmp"

    try:
        data_dir = os.path.dirname(data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(subscriptions_data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, data_file)
        logger.debug(f"订阅已成功保存到 {data_file}")
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                logger.warning("清理临时订阅文件失败: %s", temp_file)
        logger.error(f"保存订阅到 {data_file} 时出错: {e}")


def get_subscriptions() -> Dict[str, Dict[str, Any]]:
    return subscriptions_data
