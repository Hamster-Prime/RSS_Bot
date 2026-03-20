import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import data_manager
import feed_checker


class FeedCheckerTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        data_manager.subscriptions_data = {}

    async def test_build_entry_message_escapes_html(self) -> None:
        message = feed_checker._build_entry_message(
            "A&B <Feed>",
            {
                "title": '1 < 2 & 3',
                "link": 'https://example.com/?a=1&b="2"',
            },
        )

        self.assertIn("<b>A&amp;B &lt;Feed&gt;</b>", message)
        self.assertIn(">1 &lt; 2 &amp; 3<", message)
        self.assertIn('href="https://example.com/?a=1&amp;b=&quot;2&quot;"', message)

    async def test_send_telegram_message_escapes_footer(self) -> None:
        data_manager.subscriptions_data = {
            "1": {
                "rss_feeds": {},
                "custom_footer": "<Footer & more>",
                "link_preview_enabled": False,
            }
        }

        send_message = AsyncMock()
        context = SimpleNamespace(bot=SimpleNamespace(send_message=send_message))

        async def passthrough(func, *args, **kwargs):
            return await func(*args, **kwargs)

        with patch("feed_checker.retry_utils.retry_telegram_api", new=passthrough):
            await feed_checker.send_telegram_message(context, "1", "<b>Body</b>")

        kwargs = send_message.await_args.kwargs
        self.assertEqual(kwargs["text"], "<b>Body</b>\n---\n&lt;Footer &amp; more&gt;")
        self.assertTrue(kwargs["disable_web_page_preview"])

    async def test_send_failure_only_advances_last_successful_entry(self) -> None:
        feed_url = "https://example.com/feed"
        data_manager.subscriptions_data = {
            "1": {
                "rss_feeds": {
                    feed_url: {
                        "title": "Feed",
                        "keywords": [],
                        "last_entry_id": "old",
                    }
                },
                "custom_footer": None,
                "link_preview_enabled": True,
            }
        }

        parsed_feed = SimpleNamespace(
            entries=[
                {"id": "new-2", "title": "Two", "link": "https://example.com/2"},
                {"id": "new-1", "title": "One", "link": "https://example.com/1"},
                {"id": "old", "title": "Old", "link": "https://example.com/old"},
            ],
            bozo=False,
            bozo_exception=None,
        )

        async def send_side_effect(*args, **kwargs):
            if send_side_effect.calls == 0:
                send_side_effect.calls += 1
                return None
            raise RuntimeError("send failed")

        send_side_effect.calls = 0

        with patch("feed_checker.feedparser.parse", return_value=parsed_feed), patch(
            "feed_checker.send_telegram_message",
            side_effect=send_side_effect,
        ), patch("feed_checker.data_manager.save_subscriptions"):
            with self.assertRaises(RuntimeError):
                await feed_checker.check_single_feed(
                    SimpleNamespace(),
                    "1",
                    feed_url,
                    dict(data_manager.subscriptions_data["1"]["rss_feeds"][feed_url]),
                    "data/subscriptions.json",
                )

        self.assertEqual(
            data_manager.subscriptions_data["1"]["rss_feeds"][feed_url]["last_entry_id"],
            "new-1",
        )
