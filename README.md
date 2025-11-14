# Telegram RSS 订阅机器人

这是一个 Telegram 机器人，可以帮助您订阅 RSS 源并通过 Telegram 接收更新。

示例Bot : [Sanite_Ava_RSS_bot](https://t.me/Sanite_Ava_RSS_bot)

## 功能

*   添加和移除 RSS 订阅源。
*   列出当前订阅的所有 RSS 源。
*   为每个订阅源设置关键词过滤器，只接收包含特定关键词的更新。
*   管理订阅源的关键词（添加、移除、列出、全部移除）。
*   自定义推送到 Telegram 消息的页脚。
*   切换推送消息中链接预览的显示/隐藏状态。
*   定期检查 RSS 源的更新。

## 安装与配置

1.  **克隆仓库或下载文件:**
    ```bash
    git clone https://github.com/Hamster-Prime/RSS_Bot.git
    cd RSS_Bot
    ```
    或者直接下载项目文件 (`bot.py`, `requirements.txt`, `config.json.example`, `data/` 目录)。

2.  **安装依赖:**
    确保您已安装 Python 3.x。然后安装所需的库：
    ```bash
    pip install -r requirements.txt
    ```

3.  **配置机器人:**
    *   将您的 Telegram Bot Token 添加到 `config.json` 文件中。如果您没有 `config.json` 文件，可以创建一个，或者复制 `config.json.example` 并重命名为 `config.json`。
    *   **参数说明:**
        *   `telegram_token`: (必需) 您的 Telegram Bot 的 API Token。您可以从 BotFather 获取。
        *   `data_file`: (必需, 默认为 "subscriptions.json") 用于存储用户订阅数据的文件名。
        *   `check_interval_seconds`: (可选, 默认为 300) 机器人检查 RSS 源更新的频率（以秒为单位）。

## 运行机器人

配置完成后，您可以运行机器人：

```bash
python bot.py
```

机器人启动后，您就可以在 Telegram 中与它交互了。

## 命令列表

与机器人对话时，可以使用以下命令：

*   `/start` - 开始与机器人交互并显示欢迎信息。
*   `/help` - 显示帮助信息，列出所有可用命令。
*   `/add <RSS链接>` - 添加一个新的 RSS 订阅源。
    *   示例: `/add https://www.example.com/feed.xml`
*   `/remove <RSS链接或ID>` - 移除一个 RSS 订阅源。您可以使用 `/list` 命令中显示的链接或其对应的数字 ID。
    *   示例: `/remove https://www.example.com/feed.xml` 或 `/remove 1`
*   `/list` - 列出您当前所有的 RSS 订阅及其 ID 和已设置的关键词。
*   `/addkeyword <RSS链接或ID> <关键词>` - 为指定的订阅源添加关键词过滤器。只有包含该关键词的条目才会被推送。
    *   示例: `/addkeyword 1 python` 或 `/addkeyword https://www.example.com/feed.xml programming`
*   `/removekeyword <RSS链接或ID> <关键词>` - 从指定的订阅源中移除一个关键词过滤器。
    *   示例: `/removekeyword 1 python`
*   `/listkeywords <RSS链接或ID>` - 列出特定订阅源已设置的所有关键词。
    *   示例: `/listkeywords 1`
*   `/removeallkeywords <RSS链接或ID>` - 移除特定订阅源的所有关键词过滤器。
    *   示例: `/removeallkeywords 1`
*   `/setfooter [自定义文本]` - 设置推送到此聊天的消息的自定义页脚。如果不提供文本，则清除页脚。
    *   示例: `/setfooter 由我的机器人推送` 或 `/setfooter` (清除页脚)
*   `/togglepreview` - 切换推送消息中链接预览的显示/隐藏状态。默认开启预览。

## 数据存储

用户的订阅信息、关键词和设置将存储在 `data/` 目录下的 JSON 文件中（文件名由 `config.json` 中的 `data_file` 指定，默认为 `subscriptions.json`）。

## 注意事项

*   确保您的 Telegram Bot Token 正确无误。
*   机器人需要持续运行才能接收和推送 RSS 更新。
*   某些 RSS 源可能格式不规范，`feedparser` 会尝试解析，但可能会出现警告。

## 许可证

本项目采用 [MIT 许可协议](LICENSE)。
