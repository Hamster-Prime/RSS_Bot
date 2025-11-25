import logging
from typing import Any, Dict
from telegram.ext import Application, CommandHandler, ContextTypes
import config
import data_manager
import feed_checker
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def check_feeds_job_wrapper(context: ContextTypes.DEFAULT_TYPE) -> None:
    data_file = context.bot_data.get('data_file', 'data/subscriptions.json')
    await feed_checker.check_feeds_job(context, data_file)


def _register_handlers(application: Application) -> None:
    handlers_map = {
        "start": handlers.start,
        "help": handlers.help_command,
        "add": handlers.add_feed,
        "remove": handlers.remove_feed,
        "list": handlers.list_feeds,
        "addkeyword": handlers.add_keyword,
        "removekeyword": handlers.remove_keyword,
        "listkeywords": handlers.list_keywords,
        "removeallkeywords": handlers.remove_all_keywords,
        "setfooter": handlers.set_custom_footer,
        "togglepreview": handlers.toggle_link_preview,
    }
    
    for command, handler in handlers_map.items():
        application.add_handler(CommandHandler(command, handler))


def _setup_job_queue(application: Application, check_interval: int) -> None:
    if not isinstance(check_interval, int) or check_interval <= 0:
        logger.warning(f"无效的 check_interval_seconds: {check_interval}。默认为 300 秒。")
        check_interval = 300
    
    job_queue = application.job_queue
    job_queue.run_repeating(
        check_feeds_job_wrapper,
        interval=check_interval,
        first=10
    )
    
    logger.info(f"订阅源检查间隔: {check_interval} 秒")


def main() -> None:
    cfg = config.load_config()
    if not cfg:
        logger.error("配置加载失败，无法启动机器人。")
        return

    data_file = cfg.get('data_file', 'data/subscriptions.json')
    data_manager.load_subscriptions(data_file)

    telegram_token = cfg.get("telegram_token")
    if not telegram_token:
        logger.error("配置中缺少 Telegram token，无法启动机器人。")
        return

    application = Application.builder().token(telegram_token).build()
    application.bot_data['data_file'] = data_file

    _register_handlers(application)

    check_interval = cfg.get("check_interval_seconds", 300)
    _setup_job_queue(application, check_interval)

    logger.info("机器人启动中...")
    application.run_polling()
    logger.info("机器人已停止。")


if __name__ == '__main__':
    main()
