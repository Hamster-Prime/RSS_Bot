import asyncio
import logging
import feedparser
from telegram.ext import ContextTypes
from telegram import constants
import data_manager

logger = logging.getLogger(__name__)


async def send_telegram_message(context: ContextTypes.DEFAULT_TYPE, chat_id: str, text: str):
    try:
        subscriptions_data = data_manager.get_subscriptions()
        user_chat_id_str = str(chat_id)
        custom_footer = subscriptions_data.get(user_chat_id_str, {}).get("custom_footer")
        link_preview_enabled = subscriptions_data.get(user_chat_id_str, {}).get("link_preview_enabled", True)

        if custom_footer:
            text += f"\n---\n{custom_footer}"

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=constants.ParseMode.HTML,
            disable_web_page_preview=not link_preview_enabled
        )
    except Exception as e:
        logger.error(f"向 {chat_id} 发送消息时出错: {e}")


async def check_single_feed(context: ContextTypes.DEFAULT_TYPE, chat_id: str, feed_url: str, feed_config: dict, data_file: str):
    logger.info(f"正在为用户 {chat_id} 检查订阅源: {feed_url}")
    try:
        feed_content = await asyncio.to_thread(feedparser.parse, feed_url) if hasattr(asyncio, 'to_thread') else await asyncio.get_event_loop().run_in_executor(None, feedparser.parse, feed_url)
        
        if feed_content.bozo:
            logger.warning(f"用户 {chat_id} 的订阅源 {feed_url} 可能格式错误。Bozo 标记: {feed_content.bozo_exception}")

        new_entries = []
        last_known_entry_id = feed_config.get("last_entry_id")
        current_feed_latest_entry_id = None
        
        if feed_content.entries:
            latest_entry_in_fetch = feed_content.entries[0]
            current_feed_latest_entry_id = latest_entry_in_fetch.get("id") or latest_entry_in_fetch.get("link")

        temp_new_entries = []
        found_last_known = False
        if last_known_entry_id is None:
            if current_feed_latest_entry_id:
                subscriptions_data = data_manager.get_subscriptions()
                subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = current_feed_latest_entry_id
                logger.info(f"首次检查 {feed_url} (用户 {chat_id})。将 last_entry_id 设置为 {current_feed_latest_entry_id}。此周期不发送初始帖子。")
                data_manager.save_subscriptions(data_file)
            return

        for entry in feed_content.entries:
            entry_id = entry.get("id") or entry.get("link")
            if not entry_id:
                logger.warning(f"{feed_url} 中的条目缺少 'id' 和 'link'。正在跳过。")
                continue

            if last_known_entry_id == entry_id:
                found_last_known = True
                break
            temp_new_entries.append(entry)

        if not found_last_known and last_known_entry_id is not None:
            logger.warning(f"在用户 {chat_id} 的 {feed_url} 当前获取中未找到最后已知条目 ID '{last_known_entry_id}'。如果存在，则最多发送 5 个最新项目。")
            new_entries = list(reversed(temp_new_entries[:5]))
        else:
            new_entries = list(reversed(temp_new_entries))

        sent_count = 0
        latest_sent_entry_id_this_cycle = None
        subscriptions_data = data_manager.get_subscriptions()

        for entry in new_entries:
            entry_id = entry.get("id") or entry.get("link")
            title = entry.get("title", "无标题")
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            keywords = feed_config.get("keywords", [])
            if keywords:
                content_to_check = f"{title} {summary}".lower()
                match_found = False
                for kw in keywords:
                    if kw.lower() in content_to_check:
                        match_found = True
                        break
                if not match_found:
                    logger.debug(f"来自 {feed_url} 的条目 '{title}' 因用户 {chat_id} 的关键词不匹配而被跳过。")
                    continue

            message = f"<b>{feed_config.get('title', feed_url)}</b>\n<a href='{link}'>{title}</a>"
            
            await send_telegram_message(context, chat_id, message)
            sent_count += 1
            latest_sent_entry_id_this_cycle = entry_id

            if sent_count >= 5 and len(new_entries) > 7:
                await send_telegram_message(context, chat_id, f"<i>...以及来自 {feed_config.get('title', feed_url)} 的 {len(new_entries) - sent_count} 个更多新条目。</i>")
                logger.info(f"已向用户 {chat_id} 发送 {sent_count} 个来自 {feed_url} 的条目，还有更多可用 (反垃圾邮件)。")
                break

        if latest_sent_entry_id_this_cycle:
            subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = latest_sent_entry_id_this_cycle
            logger.info(f"已向用户 {chat_id} 发送 {sent_count} 个来自 {feed_url} 的新条目。已将 last_entry_id 更新为 {latest_sent_entry_id_this_cycle}。")
            data_manager.save_subscriptions(data_file)
        elif not new_entries and current_feed_latest_entry_id and \
             subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] != current_feed_latest_entry_id:
            subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = current_feed_latest_entry_id
            logger.info(f"未向用户 {chat_id} 发送来自 {feed_url} 的新条目 (例如已过滤)。已将 last_entry_id 更新为订阅源中的最新条目: {current_feed_latest_entry_id}。")
            data_manager.save_subscriptions(data_file)
        elif sent_count == 0 and new_entries:
            id_of_newest_identified_entry = new_entries[-1].get("id") or new_entries[-1].get("link")
            if id_of_newest_identified_entry:
                subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = id_of_newest_identified_entry
                logger.info(f"用户 {chat_id} 的 {feed_url} 中的所有新条目均已过滤。已将 last_entry_id 更新为 {id_of_newest_identified_entry}。")
                data_manager.save_subscriptions(data_file)

    except Exception as e:
        logger.error(f"处理用户 {chat_id} 的订阅源 {feed_url} 时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def check_feeds_job(context: ContextTypes.DEFAULT_TYPE, data_file: str) -> None:
    """检查所有RSS订阅源（并发执行）"""
    logger.info("正在运行定期订阅源检查...")
    subscriptions_data = data_manager.get_subscriptions()
    
    if not subscriptions_data:
        logger.info("没有要检查的订阅。")
        return
    
    all_feed_checks = []
    for chat_id, user_data in list(subscriptions_data.items()):
        if "rss_feeds" in user_data:
            for feed_url, feed_config in list(user_data["rss_feeds"].items()):
                all_feed_checks.append(
                    check_single_feed(context, chat_id, feed_url, dict(feed_config), data_file)
                )
    
    if all_feed_checks:
        logger.info(f"已计划 {len(all_feed_checks)} 个订阅源检查，将并发执行。")
        results = await asyncio.gather(*all_feed_checks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"订阅源检查任务 {i} 失败: {result}")
        
        logger.info("此周期的所有订阅源检查已完成。")
    else:
        logger.info("在 subscriptions_data 中未找到要检查的订阅源。")

