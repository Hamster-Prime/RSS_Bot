# Telegram RSS 订阅机器人

这是一个高性能的 Telegram RSS 订阅机器人，采用异步并发架构，支持多用户同时订阅多个 RSS 源，不会因用户数量增加而影响性能。

示例Bot : [Sanite_Ava_RSS_bot](https://t.me/Sanite_Ava_RSS_bot)

## ✨ 主要特性

*   **高性能并发处理** - 所有 RSS 订阅源同时并发检查，用户越多，检查时间不会线性增长
*   **非阻塞用户交互** - RSS 拉取在后台异步执行，用户命令即时响应
*   **模块化架构** - 代码结构清晰，易于维护和扩展
*   **添加和移除 RSS 订阅源**
*   **关键词过滤** - 为每个订阅源设置关键词过滤器，只接收包含特定关键词的更新
*   **自定义页脚** - 自定义推送到 Telegram 消息的页脚
*   **链接预览控制** - 切换推送消息中链接预览的显示/隐藏状态
*   **定期自动检查** - 可配置的 RSS 源更新检查频率

## 📁 项目结构

```
RSS_Bot/
├── bot.py                 # 主程序入口
├── config.py              # 配置管理模块
├── data_manager.py        # 数据存储和加载模块
├── feed_checker.py        # RSS订阅检查模块（并发处理）
├── handlers.py            # 命令处理器模块
├── config.json.example    # 配置文件示例
├── requirements.txt       # Python依赖包
├── data/                  # 数据存储目录
│   └── subscriptions.json # 用户订阅数据（自动生成）
└── README.md             # 本文件
```

## 🚀 安装与配置

### 1. 克隆仓库

```bash
git clone https://github.com/Hamster-Prime/RSS_Bot.git
cd RSS_Bot
```

### 2. 安装依赖

确保您已安装 **Python 3.7+**。然后安装所需的库：

```bash
pip install -r requirements.txt
```

依赖包包括：
- `python-telegram-bot` - Telegram Bot API
- `feedparser` - RSS/Atom 解析器
- `requests` - HTTP 请求库

### 3. 配置机器人

1. 复制配置文件示例：
   ```bash
   cp config.json.example config.json
   ```

2. 编辑 `config.json` 文件，填入您的配置：

   ```json
   {
     "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN",
     "data_file": "subscriptions.json",
     "check_interval_seconds": 300
   }
   ```

   **参数说明：**
   - `telegram_token`: **(必需)** 您的 Telegram Bot 的 API Token。从 [@BotFather](https://t.me/BotFather) 获取
   - `data_file`: (可选, 默认为 "subscriptions.json") 用于存储用户订阅数据的文件名
   - `check_interval_seconds`: (可选, 默认为 300) 机器人检查 RSS 源更新的频率（秒）

## 🏃 运行机器人

配置完成后，运行机器人：

```bash
python bot.py
```

机器人启动后，您会看到类似以下的日志：

```
INFO - 数据将存储在: data/subscriptions.json
INFO - 订阅已成功从 data/subscriptions.json 加载
INFO - 机器人启动中... 订阅源检查间隔: 300 秒。
INFO - 所有RSS订阅将并发检查，不会阻塞用户交互。
```

## 📖 命令列表

与机器人对话时，可以使用以下命令：

### 基础命令

*   `/start` - 开始与机器人交互并显示欢迎信息
*   `/help` - 显示帮助信息，列出所有可用命令

### 订阅管理

*   `/add <RSS链接>` - 添加一个新的 RSS 订阅源
    *   示例: `/add https://www.example.com/feed.xml`
*   `/remove <RSS链接或ID>` - 移除一个 RSS 订阅源（可使用 `/list` 中的链接或数字 ID）
    *   示例: `/remove https://www.example.com/feed.xml` 或 `/remove 1`
*   `/list` - 列出您当前所有的 RSS 订阅及其 ID 和已设置的关键词

### 关键词过滤

*   `/addkeyword <RSS链接或ID> <关键词>` - 为指定的订阅源添加关键词过滤器
    *   示例: `/addkeyword 1 python` 或 `/addkeyword https://www.example.com/feed.xml programming`
*   `/removekeyword <RSS链接或ID> <关键词>` - 从指定的订阅源中移除一个关键词过滤器
    *   示例: `/removekeyword 1 python`
*   `/listkeywords <RSS链接或ID>` - 列出特定订阅源已设置的所有关键词
    *   示例: `/listkeywords 1`
*   `/removeallkeywords <RSS链接或ID>` - 移除特定订阅源的所有关键词过滤器
    *   示例: `/removeallkeywords 1`

### 个性化设置

*   `/setfooter [自定义文本]` - 设置推送到此聊天的消息的自定义页脚。不带文本则清除页脚
    *   示例: `/setfooter 由我的机器人推送` 或 `/setfooter` (清除页脚)
*   `/togglepreview` - 切换推送消息中链接预览的显示/隐藏状态（默认开启）

## 🔧 技术架构

### 性能优化

- **异步并发处理**: 使用 `asyncio.gather()` 同时检查所有用户的 RSS 订阅源
- **非阻塞 I/O**: 所有网络请求和文件操作都使用异步执行器，不会阻塞事件循环
- **后台任务**: RSS 检查在独立的 JobQueue 中运行，不影响用户命令响应

### 模块说明

- **`bot.py`**: 主程序入口，负责初始化应用和注册处理器
- **`config.py`**: 配置文件的加载和验证
- **`data_manager.py`**: 订阅数据的加载、保存和内存管理
- **`feed_checker.py`**: RSS 订阅源的并发检查和消息推送
- **`handlers.py`**: 所有用户命令的处理逻辑

## 💾 数据存储

用户的订阅信息、关键词和设置存储在 `data/` 目录下的 JSON 文件中（文件名由 `config.json` 中的 `data_file` 指定，默认为 `subscriptions.json`）。

数据结构示例：

```json
{
  "123456789": {
    "rss_feeds": {
      "https://example.com/feed.xml": {
        "title": "示例 RSS 源",
        "keywords": ["python", "编程"],
        "last_entry_id": "entry-id-123"
      }
    },
    "custom_footer": "自定义页脚",
    "link_preview_enabled": true
  }
}
```

## ⚠️ 注意事项

*   确保您的 Telegram Bot Token 正确无误
*   机器人需要持续运行才能接收和推送 RSS 更新
*   某些 RSS 源可能格式不规范，`feedparser` 会尝试解析，但可能会出现警告
*   建议使用 `screen`、`tmux` 或 `systemd` 等服务来保持机器人持续运行
*   Python 版本要求：3.7 或更高版本

## 🔄 更新日志

### v2.0 (最新)
- ✨ 重构为模块化架构，代码更易维护
- 🚀 优化多线程操作，所有 RSS 订阅并发检查
- ⚡ 优化用户交互，RSS 拉取时机器人保持响应
- 📦 代码拆分，避免单个文件过于冗杂

### v1.0
- 初始版本

## 📝 许可证

本项目采用 [MIT 许可协议](LICENSE)。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请通过 GitHub Issues 联系。
