import logging
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import ContextTypes
import data_manager

logger = logging.getLogger(__name__)


def is_valid_url(url_string: str) -> bool:
    try:
        result = urlparse(url_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


async def schedule_message_deletion(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 5):
    async def delete_message_job(job_context):
        try:
            await job_context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(f"自动删除了消息 {message_id} (来自聊天 {chat_id})")
        except Exception as e:
            logger.warning(f"自动删除消息 {message_id} (来自聊天 {chat_id}) 失败: {e}")
    
    context.job_queue.run_once(
        delete_message_job,
        delay,
        name=f"delete_{chat_id}_{message_id}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reply_text = '你好！我是你的 RSS 订阅机器人\n\n/add <RSS链接> 添加订阅源\n/remove <RSS链接或ID> 移除订阅\n/list 列出您当前所有的 RSS 订阅\n\n更多命令请输入 /help 查看。'
    await update.message.reply_text(reply_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "以下是所有可用命令:\n\n"
        "/start - 开始与机器人交互\n"
        "/help - 显示此帮助信息\n"
        "/add <RSS链接> - 添加一个新的 RSS 订阅源\n"
        "/remove <RSS链接或ID> - 移除一个 RSS 订阅源 (使用 /list 中的链接或ID)\n"
        "/list - 列出您当前所有的 RSS 订阅\n"
        "/addkeyword <RSS链接或ID> <关键词> - 为订阅添加关键词过滤器\n"
        "/removekeyword <RSS链接或ID> <关键词> - 从订阅中移除关键词过滤器\n"
        "/listkeywords <RSS链接或ID> - 列出特定订阅的关键词\n"
        "/removeallkeywords <RSS链接或ID> - 移除特定订阅的所有关键词\n"
        "/setfooter [自定义文本] - 设置推送到此聊天的消息的自定义页脚 (不带文本则清除)\n"
        "/togglepreview - 切换推送消息中链接预览的显示/隐藏"
    )
    user_message_id = update.message.message_id
    chat_id = update.effective_chat.id
    await schedule_message_deletion(context, chat_id, user_message_id, 10)

    sent_message = await update.message.reply_text(help_text)
    await schedule_message_deletion(context, chat_id, sent_message.message_id, 10)


async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if not context.args:
        reply_message_text = "请输入 RSS 订阅源链接。用法: /add <链接>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_url = context.args[0]
    if not is_valid_url(feed_url):
        reply_message_text = f"提供的链接 '{feed_url}' 似乎无效。请检查后重试。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    subscriptions_data = data_manager.get_subscriptions()
    if chat_id not in subscriptions_data:
        subscriptions_data[chat_id] = {"rss_feeds": {}, "custom_footer": None, "link_preview_enabled": True}
    elif "rss_feeds" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["rss_feeds"] = {}
    if "custom_footer" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["custom_footer"] = None
    if "link_preview_enabled" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["link_preview_enabled"] = True

    if feed_url in subscriptions_data[chat_id]["rss_feeds"]:
        reply_message_text = f"订阅源 {feed_url} 已在您的订阅中。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    import asyncio
    if hasattr(asyncio, 'to_thread'):
        feed_title = await asyncio.to_thread(data_manager.get_feed_title, feed_url) or "未知标题"
    else:
        loop = asyncio.get_event_loop()
        feed_title = await loop.run_in_executor(None, data_manager.get_feed_title, feed_url) or "未知标题"
    
    subscriptions_data[chat_id]["rss_feeds"][feed_url] = {
        "title": feed_title,
        "keywords": [],
        "last_entry_id": None
    }
    data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))
    reply_message_text = f"订阅源 '{feed_title}' ({feed_url}) 添加成功！"
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
    logger.info(f"用户 {chat_id} 添加了订阅源: {feed_url}")


async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    subscriptions_data = data_manager.get_subscriptions()
    reply_message_text = ""
    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您还没有订阅任何 RSS 源。使用 /add <链接> 添加一个。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    message_content = "您当前的 RSS 订阅:\n"
    feeds = subscriptions_data[chat_id]["rss_feeds"]
    if not feeds:
        reply_message_text = "您还没有订阅任何 RSS 源。使用 /add <链接> 添加一个。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    for i, (url, data) in enumerate(feeds.items()):
        title = data.get('title', 'N/A')
        keywords_list = data.get('keywords', [])
        keywords_str = f" (关键词: {', '.join(keywords_list)})" if keywords_list else ""
        message_content += f"{i+1}. {title} - {url}{keywords_str}\n"
    
    sent_message = await update.message.reply_text(message_content)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if not context.args:
        reply_message_text = "请输入要移除的 RSS 订阅源链接或其 ID (来自 /list)。用法: /remove <链接或ID>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    identifier = context.args[0]
    subscriptions_data = data_manager.get_subscriptions()

    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您没有任何订阅可以移除。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feeds = subscriptions_data[chat_id]["rss_feeds"]
    feed_to_remove = None

    if identifier.isdigit():
        feed_index = int(identifier) - 1
        if 0 <= feed_index < len(feeds):
            feed_to_remove = list(feeds.keys())[feed_index]

    if not feed_to_remove and identifier in feeds:
        feed_to_remove = identifier

    if feed_to_remove:
        removed_title = feeds[feed_to_remove].get('title', feed_to_remove)
        del subscriptions_data[chat_id]["rss_feeds"][feed_to_remove]
        if not subscriptions_data[chat_id]["rss_feeds"]:
            del subscriptions_data[chat_id]
        data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))
        reply_message_text = f"订阅源 '{removed_title}' 移除成功。"
        logger.info(f"用户 {chat_id} 移除了订阅源: {feed_to_remove}")
    else:
        reply_message_text = f"找不到标识符为 '{identifier}' 的订阅源。使用 /list 查看您的订阅源及其 ID/链接。"
    
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if len(context.args) < 2:
        reply_message_text = "用法: /addkeyword <RSS链接或ID> <关键词>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_identifier = context.args[0]
    keyword_to_add = " ".join(context.args[1:]).lower()
    subscriptions_data = data_manager.get_subscriptions()

    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您没有任何订阅可以添加关键词。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feeds = subscriptions_data[chat_id]["rss_feeds"]
    target_feed_url = None

    if feed_identifier.isdigit():
        feed_index = int(feed_identifier) - 1
        if 0 <= feed_index < len(feeds):
            target_feed_url = list(feeds.keys())[feed_index]
    elif feed_identifier in feeds:
        target_feed_url = feed_identifier

    if not target_feed_url:
        reply_message_text = f"找不到标识符为 '{feed_identifier}' 的订阅源。请使用 /list 查看。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_data = subscriptions_data[chat_id]["rss_feeds"][target_feed_url]
    if "keywords" not in feed_data:
        feed_data["keywords"] = []

    if keyword_to_add in feed_data["keywords"]:
        reply_message_text = f"关键词 '{keyword_to_add}' 已存在于 '{feed_data.get('title', target_feed_url)}'。"
    else:
        feed_data["keywords"].append(keyword_to_add)
        data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))
        reply_message_text = f"关键词 '{keyword_to_add}' 已添加到 '{feed_data.get('title', target_feed_url)}'。"
        logger.info(f"用户 {chat_id} 向订阅源 {target_feed_url} 添加了关键词 '{keyword_to_add}'")
    
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def remove_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if len(context.args) < 2:
        reply_message_text = "用法: /removekeyword <RSS链接或ID> <关键词>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_identifier = context.args[0]
    keyword_to_remove = " ".join(context.args[1:]).lower()
    subscriptions_data = data_manager.get_subscriptions()

    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您没有任何订阅可以移除关键词。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feeds = subscriptions_data[chat_id]["rss_feeds"]
    target_feed_url = None

    if feed_identifier.isdigit():
        feed_index = int(feed_identifier) - 1
        if 0 <= feed_index < len(feeds):
            target_feed_url = list(feeds.keys())[feed_index]
    elif feed_identifier in feeds:
        target_feed_url = feed_identifier

    if not target_feed_url:
        reply_message_text = f"找不到标识符为 '{feed_identifier}' 的订阅源。请使用 /list 查看。"
    else:
        feed_data = subscriptions_data[chat_id]["rss_feeds"][target_feed_url]
        if keyword_to_remove in feed_data.get("keywords", []):
            feed_data["keywords"].remove(keyword_to_remove)
            data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))
            reply_message_text = f"关键词 '{keyword_to_remove}' 已从 '{feed_data.get('title', target_feed_url)}' 移除。"
            logger.info(f"用户 {chat_id} 从订阅源 {target_feed_url} 移除了关键词 '{keyword_to_remove}'")
        else:
            reply_message_text = f"关键词 '{keyword_to_remove}' 未在 '{feed_data.get('title', target_feed_url)}' 中找到。"
            
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if not context.args:
        reply_message_text = "用法: /listkeywords <RSS链接或ID>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_identifier = context.args[0]
    subscriptions_data = data_manager.get_subscriptions()

    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您没有任何订阅。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feeds = subscriptions_data[chat_id]["rss_feeds"]
    target_feed_url = None

    if feed_identifier.isdigit():
        feed_index = int(feed_identifier) - 1
        if 0 <= feed_index < len(feeds):
            target_feed_url = list(feeds.keys())[feed_index]
    elif feed_identifier in feeds:
        target_feed_url = feed_identifier

    if not target_feed_url:
        reply_message_text = f"找不到标识符为 '{feed_identifier}' 的订阅源。请使用 /list 查看。"
    else:
        feed_data = subscriptions_data[chat_id]["rss_feeds"][target_feed_url]
        keywords = feed_data.get("keywords", [])
        title = feed_data.get('title', target_feed_url)

        if keywords:
            reply_message_text = f"'{title}' 的关键词:\n- " + "\n- ".join(keywords)
        else:
            reply_message_text = f"'{title}' 未设置关键词。将发送所有新项目。"
            
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def remove_all_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    reply_message_text = ""
    if not context.args:
        reply_message_text = "用法: /removeallkeywords <RSS链接或ID>"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feed_identifier = context.args[0]
    subscriptions_data = data_manager.get_subscriptions()

    if chat_id not in subscriptions_data or not subscriptions_data[chat_id].get("rss_feeds"):
        reply_message_text = "您没有任何订阅。"
        sent_message = await update.message.reply_text(reply_message_text)
        await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
        return

    feeds = subscriptions_data[chat_id]["rss_feeds"]
    target_feed_url = None

    if feed_identifier.isdigit():
        feed_index = int(feed_identifier) - 1
        if 0 <= feed_index < len(feeds):
            target_feed_url = list(feeds.keys())[feed_index]
    elif feed_identifier in feeds:
        target_feed_url = feed_identifier

    if not target_feed_url:
        reply_message_text = f"找不到标识符为 '{feed_identifier}' 的订阅源。请使用 /list 查看。"
    else:
        feed_data = subscriptions_data[chat_id]["rss_feeds"][target_feed_url]
        if "keywords" in feed_data and feed_data["keywords"]:
            feed_data["keywords"] = []
            data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))
            reply_message_text = f"已成功移除订阅源 '{feed_data.get('title', target_feed_url)}' 的所有关键词。"
            logger.info(f"用户 {chat_id} 移除了订阅源 {target_feed_url} 的所有关键词。")
        else:
            reply_message_text = f"订阅源 '{feed_data.get('title', target_feed_url)}' 原本就没有设置关键词。"
            
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def set_custom_footer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    subscriptions_data = data_manager.get_subscriptions()
    if chat_id not in subscriptions_data:
        subscriptions_data[chat_id] = {"rss_feeds": {}, "custom_footer": None, "link_preview_enabled": True}
    elif "custom_footer" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["custom_footer"] = None
    if "link_preview_enabled" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["link_preview_enabled"] = True

    footer_text = " ".join(context.args) if context.args else None

    subscriptions_data[chat_id]["custom_footer"] = footer_text
    data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))

    reply_message_text = ""
    if footer_text:
        reply_message_text = f"自定义页脚已设置为: \n{footer_text}"
    else:
        reply_message_text = "自定义页脚已清除。"
    
    logger.info(f"用户 {chat_id} 将自定义页脚设置为: '{footer_text}'")
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def toggle_link_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    subscriptions_data = data_manager.get_subscriptions()
    if chat_id not in subscriptions_data:
        subscriptions_data[chat_id] = {"rss_feeds": {}, "custom_footer": None, "link_preview_enabled": True}
    elif "link_preview_enabled" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["link_preview_enabled"] = True

    current_status = subscriptions_data[chat_id].get("link_preview_enabled", True)
    new_status = not current_status
    subscriptions_data[chat_id]["link_preview_enabled"] = new_status
    data_manager.save_subscriptions(context.bot_data.get('data_file', 'data/subscriptions.json'))

    status_text = "开启" if new_status else "关闭"
    reply_message_text = f"链接预览已切换为: {status_text}。"
    
    logger.info(f"用户 {chat_id} 将链接预览切换为: {status_text}")
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)

