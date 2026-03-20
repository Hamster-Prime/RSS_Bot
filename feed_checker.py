import asyncio
import html
import logging
from typing import Any, Dict, Optional

import feedparser
from telegram import constants
from telegram.ext import ContextTypes

import data_manager
import retry_utils

logger = logging.getLogger(__name__)

MAX_SENT_ENTRIES_PER_CYCLE = 5
SUMMARY_MESSAGE_THRESHOLD = 7


async def send_telegram_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str,
    text: str
) -> None:
    subscriptions_data = data_manager.get_subscriptions()
    user_chat_id_str = str(chat_id)
    user_data = subscriptions_data.get(user_chat_id_str, {})
    custom_footer = user_data.get("custom_footer")
    link_preview_enabled = user_data.get("link_preview_enabled", True)

    if custom_footer:
        text = f"{text}\n---\n{html.escape(str(custom_footer), quote=False)}"

    await retry_utils.retry_telegram_api(
        context.bot.send_message,
        chat_id=chat_id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        disable_web_page_preview=not link_preview_enabled
    )


def _get_entry_id(entry: Dict[str, Any]) -> Optional[str]:
    return entry.get("id") or entry.get("link")


def _matches_keywords(entry: Dict[str, Any], keywords: list) -> bool:
    if not keywords:
        return True

    title = entry.get("title", "")
    summary = entry.get("summary", "")
    content = ""
    entry_content = entry.get("content")

    if isinstance(entry_content, list):
        content = " ".join(
            str(item.get("value", ""))
            for item in entry_content
            if isinstance(item, dict)
        )

    content_to_check = f"{title} {summary} {content}".lower()
    return any(kw.lower() in content_to_check for kw in keywords)


def _build_entry_message(feed_title: str, entry: Dict[str, Any]) -> str:
    safe_feed_title = html.escape(feed_title, quote=False)
    safe_title = html.escape(entry.get("title", "无标题"), quote=False)
    link = entry.get("link", "")

    if link:
        safe_link = html.escape(str(link), quote=True)
        return f'<b>{safe_feed_title}</b>\n<a href="{safe_link}">{safe_title}</a>'

    return f"<b>{safe_feed_title}</b>\n{safe_title}"


def _build_overflow_message(feed_title: str, remaining: int) -> str:
    safe_feed_title = html.escape(feed_title, quote=False)
    return f"<i>以及来自 {safe_feed_title} 的另外 {remaining} 条更新未在本轮发送。</i>"


def _update_last_entry_id(
    chat_id: str,
    feed_url: str,
    entry_id: str,
    data_file: str
) -> None:
    subscriptions_data = data_manager.get_subscriptions()
    if chat_id in subscriptions_data and feed_url in subscriptions_data[chat_id].get("rss_feeds", {}):
        subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = entry_id
        data_manager.save_subscriptions(data_file)


async def check_single_feed(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str,
    feed_url: str,
    feed_config: Dict[str, Any],
    data_file: str
) -> None:
    logger.info(f"正在为用户 {chat_id} 检查订阅源: {feed_url}")

    try:
        if hasattr(asyncio, "to_thread"):
            feed_content = await asyncio.to_thread(feedparser.parse, feed_url)
        else:
            loop = asyncio.get_event_loop()
            feed_content = await loop.run_in_executor(None, feedparser.parse, feed_url)

        if feed_content.bozo:
            logger.warning(
                "用户 %s 的订阅源 %s 可能存在格式问题: %s",
                chat_id,
                feed_url,
                feed_content.bozo_exception,
            )

        last_known_entry_id = feed_config.get("last_entry_id")
        current_feed_latest_entry_id = None

        if feed_content.entries:
            latest_entry = feed_content.entries[0]
            current_feed_latest_entry_id = _get_entry_id(latest_entry)

        if last_known_entry_id is None:
            if current_feed_latest_entry_id:
                _update_last_entry_id(chat_id, feed_url, current_feed_latest_entry_id, data_file)
                logger.info(
                    "首次检查 %s (用户 %s)，已将 last_entry_id 设置为 %s，本轮不推送历史内容。",
                    feed_url,
                    chat_id,
                    current_feed_latest_entry_id,
                )
            return

        temp_new_entries = []
        found_last_known = False

        for entry in feed_content.entries:
            entry_id = _get_entry_id(entry)
            if not entry_id:
                logger.warning("%s 中存在缺少 id/link 的条目，已跳过。", feed_url)
                continue

            if last_known_entry_id == entry_id:
                found_last_known = True
                break

            temp_new_entries.append(entry)

        if not found_last_known and last_known_entry_id is not None:
            logger.warning(
                "用户 %s 的 %s 未找到上次记录的条目 %s，本轮最多补发 %s 条。",
                chat_id,
                feed_url,
                last_known_entry_id,
                MAX_SENT_ENTRIES_PER_CYCLE,
            )
            new_entries = list(reversed(temp_new_entries[:MAX_SENT_ENTRIES_PER_CYCLE]))
        else:
            new_entries = list(reversed(temp_new_entries))

        sent_count = 0
        latest_sent_entry_id_this_cycle = None
        keywords = feed_config.get("keywords", [])
        feed_title = feed_config.get("title", feed_url)

        for entry in new_entries:
            if not _matches_keywords(entry, keywords):
                logger.debug(
                    "用户 %s 的订阅源 %s 中有条目未匹配关键字，已跳过。",
                    chat_id,
                    feed_url,
                )
                continue

            entry_id = _get_entry_id(entry)
            message = _build_entry_message(feed_title, entry)

            try:
                await send_telegram_message(context, chat_id, message)
            except Exception:
                if latest_sent_entry_id_this_cycle:
                    _update_last_entry_id(
                        chat_id,
                        feed_url,
                        latest_sent_entry_id_this_cycle,
                        data_file,
                    )
                raise

            sent_count += 1
            latest_sent_entry_id_this_cycle = entry_id

            if sent_count >= MAX_SENT_ENTRIES_PER_CYCLE and len(new_entries) > SUMMARY_MESSAGE_THRESHOLD:
                remaining = len(new_entries) - sent_count
                try:
                    await send_telegram_message(
                        context,
                        chat_id,
                        _build_overflow_message(feed_title, remaining),
                    )
                except Exception as exc:
                    logger.warning(
                        "用户 %s 的订阅源 %s 摘要消息发送失败: %s",
                        chat_id,
                        feed_url,
                        exc,
                    )

                logger.info(
                    "已向用户 %s 发送来自 %s 的 %s 条更新，剩余 %s 条留待后续轮次发送。",
                    chat_id,
                    feed_url,
                    sent_count,
                    remaining,
                )
                break

        if latest_sent_entry_id_this_cycle:
            _update_last_entry_id(chat_id, feed_url, latest_sent_entry_id_this_cycle, data_file)
            logger.info(
                "已向用户 %s 发送来自 %s 的 %s 条新条目，last_entry_id 更新为 %s。",
                chat_id,
                feed_url,
                sent_count,
                latest_sent_entry_id_this_cycle,
            )
        elif not new_entries and current_feed_latest_entry_id:
            subscriptions_data = data_manager.get_subscriptions()
            current_last_id = subscriptions_data.get(chat_id, {}).get("rss_feeds", {}).get(feed_url, {}).get("last_entry_id")
            if current_last_id != current_feed_latest_entry_id:
                _update_last_entry_id(chat_id, feed_url, current_feed_latest_entry_id, data_file)
                logger.info(
                    "用户 %s 的 %s 本轮无可发送条目，last_entry_id 对齐到最新条目 %s。",
                    chat_id,
                    feed_url,
                    current_feed_latest_entry_id,
                )
        elif sent_count == 0 and new_entries:
            id_of_newest_identified_entry = _get_entry_id(new_entries[-1])
            if id_of_newest_identified_entry:
                _update_last_entry_id(chat_id, feed_url, id_of_newest_identified_entry, data_file)
                logger.info(
                    "用户 %s 的 %s 新条目均被过滤，last_entry_id 更新为 %s。",
                    chat_id,
                    feed_url,
                    id_of_newest_identified_entry,
                )

    except Exception:
        logger.exception("处理用户 %s 的订阅源 %s 时出错", chat_id, feed_url)
        raise


async def check_feeds_job(context: ContextTypes.DEFAULT_TYPE, data_file: str) -> None:
    logger.info("正在运行定期订阅源检查...")
    subscriptions_data = data_manager.get_subscriptions()

    if not subscriptions_data:
        logger.info("当前没有需要检查的订阅。")
        return

    all_feed_checks = []
    feed_check_targets = []

    for chat_id, user_data in list(subscriptions_data.items()):
        feeds = user_data.get("rss_feeds", {})
        for feed_url, feed_config in list(feeds.items()):
            feed_check_targets.append((chat_id, feed_url))
            all_feed_checks.append(
                check_single_feed(context, chat_id, feed_url, dict(feed_config), data_file)
            )

    if not all_feed_checks:
        logger.info("订阅数据中没有可检查的订阅源。")
        return

    logger.info("计划检查 %s 个订阅源，将并发执行。", len(all_feed_checks))
    results = await asyncio.gather(*all_feed_checks, return_exceptions=True)

    error_count = 0
    for (chat_id, feed_url), result in zip(feed_check_targets, results):
        if isinstance(result, Exception):
            error_count += 1
            logger.error("订阅源检查失败: user=%s feed=%s error=%s", chat_id, feed_url, result)

    if error_count > 0:
        logger.warning("本轮有 %s/%s 个订阅源检查失败。", error_count, len(all_feed_checks))
    else:
        logger.info("本轮所有订阅源检查已完成。")
