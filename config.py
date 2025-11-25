import json
import os
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.json'
DATA_DIR = 'data'


def load_config():
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

        data_file = os.path.join(DATA_DIR, data_file_name)
        config['data_file'] = data_file
        logger.info(f"数据将存储在: {data_file}")
        return config
    except json.JSONDecodeError:
        logger.error(f"解码 {CONFIG_FILE} 出错。请确保它是有效的 JSON。")
        return None
    except Exception as e:
        logger.error(f"加载配置出错: {e}")
        return None

