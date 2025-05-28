import logging
import json
import os
import feedparser
from urllib.parse import urlparse
import asyncio
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, JobQueue

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.json'
DATA_DIR = 'data'
DATA_FILE = ''

subscriptions_data = {}

def load_config():
    global DATA_FILE, DATA_DIR
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"未找到 {CONFIG_FILE}。请将 config.json.example 复制为 {CONFIG_FILE} 并填写。")
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if "telegram_token" not in config or not config["telegram_token"]:
            logger.error("config.json 中缺少 Telegram token。")
            return None
        os.makedirs(DATA_DIR, exist_ok=True)
        data_file_name = config.get("data_file", "subscriptions.json")
        if '/' in data_file_name or '\\' in data_file_name:
            logger.warning(f"config.json 中的 data_file ('{data_file_name}') 应为文件名，而不是路径。仅使用文件名部分。")
            data_file_name = os.path.basename(data_file_name)

        DATA_FILE = os.path.join(DATA_DIR, data_file_name)
        logger.info(f"数据将存储在: {DATA_FILE}")
        return config
    except json.JSONDecodeError:
        logger.error(f"解码 {CONFIG_FILE} 出错。请确保它是有效的 JSON。")
        return None
    except Exception as e:
        logger.error(f"加载配置出错: {e}")
        return None

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_context = context.job.data
    chat_id = job_context["chat_id"]
    message_id = job_context["message_id"]
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.debug(f"自动删除了消息 {message_id} (来自聊天 {chat_id})")
    except Exception as e:
        logger.warning(f"自动删除消息 {message_id} (来自聊天 {chat_id}) 失败: {e}")

async def schedule_message_deletion(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 5):
    context.job_queue.run_once(
        delete_message_job,
        delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"delete_{chat_id}_{message_id}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reply_text = '你好！我是你的 RSS 订阅机器人\n\n/add <RSS链接> 添加订阅源\n/remove <RSS链接或ID> 移除订阅\n/list 列出您当前所有的 RSS 订阅\n\n更多命令请输入 /help 查看。'
    sent_message = await update.message.reply_text(reply_text)

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

def is_valid_url(url_string: str) -> bool:
    try:
        result = urlparse(url_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_feed_title(feed_url: str) -> str | None:
    try:
        feed = feedparser.parse(feed_url)
        if feed.feed and feed.feed.title:
            return feed.feed.title
        logger.warning(f"无法获取订阅源的标题: {feed_url}")
    except Exception as e:
        logger.error(f"获取订阅源 {feed_url} 标题时出错: {e}")
    return None

def load_subscriptions() -> dict:
    global subscriptions_data
    if not os.path.exists(DATA_FILE):
        logger.info(f"未找到 {DATA_FILE}。初始化为空订阅。")
        subscriptions_data = {}
        return subscriptions_data
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
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

        logger.info(f"订阅已成功从 {DATA_FILE} 加载")
    except json.JSONDecodeError:
        logger.error(f"解码 {DATA_FILE} 出错。初始化为空订阅。")
        subscriptions_data = {}
    except Exception as e:
        logger.error(f"从 {DATA_FILE} 加载订阅出错: {e}。初始化为空订阅。")
        subscriptions_data = {}
    return subscriptions_data

def save_subscriptions() -> None:
    global subscriptions_data
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(subscriptions_data, f, indent=4, ensure_ascii=False)
        logger.debug(f"订阅已成功保存到 {DATA_FILE}")
    except Exception as e:
        logger.error(f"保存订阅到 {DATA_FILE} 时出错: {e}")


def main() -> None:
    config = load_config()
    if not config:
        return

    load_subscriptions()

    telegram_token = config.get("telegram_token")

    application = Application.builder().token(telegram_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("remove", remove_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("addkeyword", add_keyword))
    application.add_handler(CommandHandler("removekeyword", remove_keyword))
    application.add_handler(CommandHandler("listkeywords", list_keywords))
    application.add_handler(CommandHandler("removeallkeywords", remove_all_keywords))
    application.add_handler(CommandHandler("setfooter", set_custom_footer))
    application.add_handler(CommandHandler("togglepreview", toggle_link_preview))

    job_queue = application.job_queue
    check_interval = config.get("check_interval_seconds", 300)
    if not isinstance(check_interval, int) or check_interval <= 0:
        logger.warning(f"无效的 check_interval_seconds: {check_interval}。默认为 300 秒。")
        check_interval = 300
    job_queue.run_repeating(check_feeds_job, interval=check_interval, first=10)

    logger.info(f"机器人启动中... 订阅源检查间隔: {check_interval} 秒。")
    application.run_polling()
    logger.info("机器人已停止。")

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

    feed_title = get_feed_title(feed_url) or "未知标题"
    subscriptions_data[chat_id]["rss_feeds"][feed_url] = {
        "title": feed_title,
        "keywords": [],
        "last_entry_id": None
    }
    save_subscriptions()
    reply_message_text = f"订阅源 '{feed_title}' ({feed_url}) 添加成功！"
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)
    logger.info(f"用户 {chat_id} 添加了订阅源: {feed_url}")

async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

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
        save_subscriptions()
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
        save_subscriptions()
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
            save_subscriptions()
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
            save_subscriptions()
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

    if chat_id not in subscriptions_data:
        subscriptions_data[chat_id] = {"rss_feeds": {}, "custom_footer": None, "link_preview_enabled": True}
    elif "custom_footer" not in subscriptions_data[chat_id]:
         subscriptions_data[chat_id]["custom_footer"] = None
    if "link_preview_enabled" not in subscriptions_data[chat_id]:
        subscriptions_data[chat_id]["link_preview_enabled"] = True


    footer_text = " ".join(context.args) if context.args else None

    subscriptions_data[chat_id]["custom_footer"] = footer_text
    save_subscriptions()

    reply_message_text = ""
    if footer_text:
        reply_message_text = f"自定义页脚已设置为: \n{footer_text}"
    else:
        reply_message_text = "自定义页脚已清除。"
    
    logger.info(f"用户 {chat_id} 将自定义页脚设置为: '{footer_text}'")
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)

async def toggle_link_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """切换链接预览的显示状态。"""
    user_message_id = update.message.message_id
    chat_id_int = update.effective_chat.id
    chat_id = str(chat_id_int)
    await schedule_message_deletion(context, chat_id_int, user_message_id, 5)

    if chat_id not in subscriptions_data:
        subscriptions_data[chat_id] = {"rss_feeds": {}, "custom_footer": None, "link_preview_enabled": True}
    elif "link_preview_enabled" not in subscriptions_data[chat_id]:
         subscriptions_data[chat_id]["link_preview_enabled"] = True

    current_status = subscriptions_data[chat_id].get("link_preview_enabled", True)
    new_status = not current_status
    subscriptions_data[chat_id]["link_preview_enabled"] = new_status
    save_subscriptions()

    status_text = "开启" if new_status else "关闭"
    reply_message_text = f"链接预览已切换为: {status_text}。"
    
    logger.info(f"用户 {chat_id} 将链接预览切换为: {status_text}")
    sent_message = await update.message.reply_text(reply_message_text)
    await schedule_message_deletion(context, chat_id_int, sent_message.message_id, 5)


async def send_telegram_message(context: ContextTypes.DEFAULT_TYPE, chat_id: str, text: str):
    try:
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

async def check_single_feed(context: ContextTypes.DEFAULT_TYPE, chat_id: str, feed_url: str, feed_config: dict):
    logger.info(f"正在为用户 {chat_id} 检查订阅源: {feed_url}")
    try:
        feed_content = feedparser.parse(feed_url)
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
                subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = current_feed_latest_entry_id
                logger.info(f"首次检查 {feed_url} (用户 {chat_id})。将 last_entry_id 设置为 {current_feed_latest_entry_id}。此周期不发送初始帖子。")
                save_subscriptions()
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

            if sent_count >= 5 and len(new_entries) > 7 :
                await send_telegram_message(context, chat_id, f"<i>...以及来自 {feed_config.get('title', feed_url)} 的 {len(new_entries) - sent_count} 个更多新条目。</i>")
                logger.info(f"已向用户 {chat_id} 发送 {sent_count} 个来自 {feed_url} 的条目，还有更多可用 (反垃圾邮件)。")
                break

        if latest_sent_entry_id_this_cycle:
            subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = latest_sent_entry_id_this_cycle
            logger.info(f"已向用户 {chat_id} 发送 {sent_count} 个来自 {feed_url} 的新条目。已将 last_entry_id 更新为 {latest_sent_entry_id_this_cycle}。")
            save_subscriptions()
        elif not new_entries and current_feed_latest_entry_id and \
             subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] != current_feed_latest_entry_id:
            subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = current_feed_latest_entry_id
            logger.info(f"未向用户 {chat_id} 发送来自 {feed_url} 的新条目 (例如已过滤)。已将 last_entry_id 更新为订阅源中的最新条目: {current_feed_latest_entry_id}。")
            save_subscriptions()
        elif sent_count == 0 and new_entries:
            id_of_newest_identified_entry = new_entries[-1].get("id") or new_entries[-1].get("link")
            if id_of_newest_identified_entry:
                 subscriptions_data[chat_id]["rss_feeds"][feed_url]["last_entry_id"] = id_of_newest_identified_entry
                 logger.info(f"用户 {chat_id} 的 {feed_url} 中的所有新条目均已过滤。已将 last_entry_id 更新为 {id_of_newest_identified_entry}。")
                 save_subscriptions()


    except Exception as e:
        logger.error(f"处理用户 {chat_id} 的订阅源 {feed_url} 时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def check_feeds_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("正在运行定期订阅源检查...")
    if not subscriptions_data:
        logger.info("没有要检查的订阅。")
        return
    
    all_feed_checks = []
    for chat_id, user_data in list(subscriptions_data.items()):
        if "rss_feeds" in user_data:
            for feed_url, feed_config in list(user_data["rss_feeds"].items()):
                all_feed_checks.append(check_single_feed(context, chat_id, feed_url, dict(feed_config)))
    
    if all_feed_checks:
        logger.info(f"已计划 {len(all_feed_checks)} 个订阅源检查。")
        await asyncio.gather(*all_feed_checks, return_exceptions=True)
        logger.info("此周期的所有订阅源检查已完成。")
    else:
        logger.info("在 subscriptions_data 中未找到要检查的订阅源。")

if __name__ == '__main__':
    main()