import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import data_manager
import handlers


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        data_manager.subscriptions_data = {}

    async def test_remove_feed_preserves_user_preferences(self) -> None:
        data_manager.subscriptions_data = {
            "123": {
                "rss_feeds": {
                    "https://example.com/feed": {
                        "title": "Feed",
                        "keywords": [],
                        "last_entry_id": None,
                    }
                },
                "custom_footer": "Footer",
                "link_preview_enabled": False,
            }
        }

        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        context = SimpleNamespace(
            args=["1"],
            bot_data={"data_file": "data/subscriptions.json"},
        )

        with patch("handlers.data_manager.save_subscriptions"):
            await handlers.remove_feed(update, context)

        self.assertIn("123", data_manager.subscriptions_data)
        self.assertEqual(data_manager.subscriptions_data["123"]["rss_feeds"], {})
        self.assertEqual(data_manager.subscriptions_data["123"]["custom_footer"], "Footer")
        self.assertFalse(data_manager.subscriptions_data["123"]["link_preview_enabled"])


class DataManagerTests(unittest.TestCase):
    def tearDown(self) -> None:
        data_manager.subscriptions_data = {}

    def test_load_subscriptions_normalizes_feed_fields(self) -> None:
        data_file = Path("tests/.tmp_subscriptions.json")
        self.addCleanup(lambda: data_file.unlink(missing_ok=True))
        data_file.write_text(
            json.dumps(
                {
                    "100": {
                        "rss_feeds": {
                            "https://example.com/feed": {
                                "title": 123,
                                "keywords": ["python", 42, ""],
                                "last_entry_id": 99,
                            }
                        },
                        "custom_footer": None,
                        "link_preview_enabled": "false",
                    }
                }
            ),
            encoding="utf-8",
        )

        loaded = data_manager.load_subscriptions(str(data_file))
        feed_data = loaded["100"]["rss_feeds"]["https://example.com/feed"]

        self.assertEqual(feed_data["title"], "123")
        self.assertEqual(feed_data["keywords"], ["python", "42"])
        self.assertEqual(feed_data["last_entry_id"], "99")
        self.assertFalse(loaded["100"]["link_preview_enabled"])

    def test_load_subscriptions_skips_invalid_user_payload(self) -> None:
        data_file = Path("tests/.tmp_subscriptions.json")
        self.addCleanup(lambda: data_file.unlink(missing_ok=True))
        data_file.write_text(
            json.dumps(
                {
                    "100": {
                        "rss_feeds": {},
                        "custom_footer": None,
                        "link_preview_enabled": True,
                    },
                    "bad": "oops",
                }
            ),
            encoding="utf-8",
        )

        loaded = data_manager.load_subscriptions(str(data_file))

        self.assertIn("100", loaded)
        self.assertNotIn("bad", loaded)
