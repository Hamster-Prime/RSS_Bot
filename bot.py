import logging
from telegram.ext import Application, CommandHandler
import config
import data_manager
import feed_checker
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def check_feeds_job_wrapper(context):
    data_file = context.bot_data.get('data_file', 'data/subscriptions.json')
    await feed_checker.check_feeds_job(context, data_file)


def main() -> None:
    cfg = config.load_config()
    if not cfg:
        return

    data_file = cfg.get('data_file', 'data/subscriptions.json')
    data_manager.load_subscriptions(data_file)

    telegram_token = cfg.get("telegram_token")

    application = Application.builder().token(telegram_token).build()
    
    application.bot_data['data_file'] = data_file

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("add", handlers.add_feed))
    application.add_handler(CommandHandler("remove", handlers.remove_feed))
    application.add_handler(CommandHandler("list", handlers.list_feeds))
    application.add_handler(CommandHandler("addkeyword", handlers.add_keyword))
    application.add_handler(CommandHandler("removekeyword", handlers.remove_keyword))
    application.add_handler(CommandHandler("listkeywords", handlers.list_keywords))
    application.add_handler(CommandHandler("removeallkeywords", handlers.remove_all_keywords))
    application.add_handler(CommandHandler("setfooter", handlers.set_custom_footer))
    application.add_handler(CommandHandler("togglepreview", handlers.toggle_link_preview))

    job_queue = application.job_queue
    check_interval = cfg.get("check_interval_seconds", 300)
    if not isinstance(check_interval, int) or check_interval <= 0:
        logger.warning(f"无效的 check_interval_seconds: {check_interval}。默认为 300 秒。")
        check_interval = 300
    
    job_queue.run_repeating(
        check_feeds_job_wrapper, 
        interval=check_interval, 
        first=10
    )

    logger.info(f"机器人启动中... 订阅源检查间隔: {check_interval} 秒。")
    logger.info("所有RSS订阅将并发检查，不会阻塞用户交互。")
    application.run_polling()
    logger.info("机器人已停止。")


if __name__ == '__main__':
    main()
