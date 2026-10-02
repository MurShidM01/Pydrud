"""
Unit tests for the bridge protocol layer.
"""

import unittest
from pydrud.core.bridge import BridgeProtocol


class TestBridgeProtocol(unittest.TestCase):
    def setUp(self):
        self.bridge = BridgeProtocol()

    def test_encode_command(self):
        msg = self.bridge.encode_command("toast", message="Hello")
        self.assertIn("toast", msg)
        self.assertIn("Hello", msg)
        self.assertTrue(msg.endswith("\n"))

    def test_encode_full_render(self):
        tree = {"type": "Container", "key": "root"}
        msg = self.bridge.encode_full_render(tree)
        self.assertIn("full_render", msg)
        self.assertIn("Container", msg)

    def test_encode_render_with_patches(self):
        patches = [{"op": "create", "key": "k1"}]
        msg = self.bridge.encode_render(patches)
        self.assertIn("render", msg)
        self.assertIn("create", msg)

    def test_decode_message(self):
        msg = self.bridge.decode_message('{"type": "click", "key": "k1"}')
        self.assertIsNotNone(msg)
        self.assertEqual(msg["type"], "click")
        self.assertEqual(msg["key"], "k1")

    def test_decode_empty_line(self):
        self.assertIsNone(self.bridge.decode_message(""))
        self.assertIsNone(self.bridge.decode_message("  "))

    def test_decode_invalid_json(self):
        self.assertIsNone(self.bridge.decode_message("{bad}"))

    def test_decode_ready_message(self):
        msg = self.bridge.decode_message('{"type": "ready", "key": "", "data": {}}')
        self.assertEqual(msg["type"], "ready")


if __name__ == "__main__":
    unittest.main()
