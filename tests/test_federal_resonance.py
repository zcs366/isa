#!/usr/bin/env python3
"""
联邦共振系统 · 测试套件
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from federal_resonance import (
    agent_online, agent_wink, agent_offline,
    list_undelivered_winks, _make_recall_record
)


class TestFederalResonance(unittest.TestCase):
    """联邦共振核心功能测试"""

    def setUp(self):
        # 模拟recall_append.py返回成功
        self.recall_patcher = patch(
            "federal_resonance._make_recall_record",
            return_value=True
        )
        self.mock_recall = self.recall_patcher.start()

    def tearDown(self):
        self.recall_patcher.stop()

    def test_agent_online(self):
        """Agent上线应调用recall_append"""
        result = agent_online("test_agent", detail="上线测试")
        self.assertTrue(result)
        self.mock_recall.assert_called_once()
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["type"], "agent_online")
        self.assertEqual(call_args["agent_id"], "test_agent")
        self.assertIn("online_at", call_args)

    def test_agent_online_with_session(self):
        """上线应携带session_id"""
        result = agent_online("test_agent", session_id="session_001")
        self.assertTrue(result)
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["session_id"], "session_001")

    def test_agent_wink(self):
        """wink应包含完整信号信息"""
        result = agent_wink(
            from_agent="octopus", to_agent="junshi",
            signal_type="delivery", summary="章鱼MVP完成"
        )
        self.assertTrue(result)
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["type"], "wink")
        self.assertEqual(call_args["from_agent"], "octopus")
        self.assertEqual(call_args["to_agent"], "junshi")
        self.assertEqual(call_args["signal_type"], "delivery")
        self.assertEqual(call_args["payload"]["summary"], "章鱼MVP完成")
        self.assertIsNone(call_args["delivered_at"])

    def test_agent_wink_with_deliverable(self):
        """wink可携带交付物路径"""
        result = agent_wink(
            from_agent="octopus", to_agent="junshi",
            signal_type="delivery", summary="交付完成",
            deliverable_path="reports/exec-report-001.md"
        )
        self.assertTrue(result)
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["payload"]["deliverable_path"], "reports/exec-report-001.md")

    def test_agent_wink_requires_response(self):
        """wink可标记需要回复"""
        result = agent_wink(
            from_agent="octopus", to_agent="junshi",
            signal_type="alert", summary="需要决策",
            requires_response=True
        )
        self.assertTrue(result)
        call_args = self.mock_recall.call_args[0][0]
        self.assertTrue(call_args["requires_response"])

    def test_agent_wink_broadcast(self):
        """to_agent='*'表示广播"""
        result = agent_wink(
            from_agent="octopus", to_agent="*",
            signal_type="handshake", summary="联邦共振上线"
        )
        self.assertTrue(result)

    def test_agent_offline(self):
        """Agent下线应记录offline_at"""
        result = agent_offline("test_agent")
        self.assertTrue(result)
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["type"], "agent_offline")
        self.assertEqual(call_args["agent_id"], "test_agent")
        self.assertIn("offline_at", call_args)

    def test_list_undelivered_winks(self):
        """扫描应只返回delivered_at=null的wink"""
        recall_text = "\n".join([
            json.dumps({"type": "wink", "from_agent": "a", "to_agent": "b",
                       "signal_type": "delivery", "payload": {"summary": "s1"},
                       "delivered_at": None, "ts": "2026-01-01T00:00:00"}),
            json.dumps({"type": "wink", "from_agent": "a", "to_agent": "b",
                       "signal_type": "delivery", "payload": {"summary": "s2"},
                       "delivered_at": "2026-01-01T01:00:00", "ts": "2026-01-01T00:30:00"}),
            json.dumps({"type": "agent_online", "agent_id": "test"}),
        ])

        mock_open = unittest.mock.mock_open(read_data=recall_text)
        with patch("builtins.open", mock_open):
            with patch("os.path.exists", return_value=True):
                winks = list_undelivered_winks(target_agent="b")

        self.assertEqual(len(winks), 1)
        self.assertEqual(winks[0]["payload"]["summary"], "s1")

    def test_list_undelivered_winks_no_file(self):
        """RECALL文件不存在时返回空列表"""
        with patch("os.path.exists", return_value=False):
            winks = list_undelivered_winks()
        self.assertEqual(winks, [])

    def test_list_undelivered_multiple_agents(self):
        """应支持按目标Agent过滤"""
        recall_text = "\n".join([
            json.dumps({"type": "wink", "from_agent": "a", "to_agent": "junshi",
                       "signal_type": "delivery", "payload": {"summary": "给军师"},
                       "delivered_at": None, "ts": "t1"}),
            json.dumps({"type": "wink", "from_agent": "b", "to_agent": "isa",
                       "signal_type": "delivery", "payload": {"summary": "给ISA"},
                       "delivered_at": None, "ts": "t2"}),
        ])
        mock_open = unittest.mock.mock_open(read_data=recall_text)
        with patch("builtins.open", mock_open):
            with patch("os.path.exists", return_value=True):
                winks = list_undelivered_winks(target_agent="junshi")
        self.assertEqual(len(winks), 1)
        self.assertEqual(winks[0]["payload"]["summary"], "给军师")

    def test_list_undelivered_all(self):
        """target_agent=None返回所有未投递wink"""
        recall_text = "\n".join([
            json.dumps({"type": "wink", "from_agent": "a", "to_agent": "b",
                       "signal_type": "delivery", "payload": {"summary": "s1"},
                       "delivered_at": None, "ts": "t1"}),
            json.dumps({"type": "wink", "from_agent": "c", "to_agent": "d",
                       "signal_type": "delivery", "payload": {"summary": "s2"},
                       "delivered_at": None, "ts": "t2"}),
        ])
        mock_open = unittest.mock.mock_open(read_data=recall_text)
        with patch("builtins.open", mock_open):
            with patch("os.path.exists", return_value=True):
                winks = list_undelivered_winks()
        self.assertEqual(len(winks), 2)

    def test_broadcast_wink_visible_to_all(self):
        """广播wink(to_agent='*')应对所有Agent可见"""
        recall_text = "\n".join([
            json.dumps({"type": "wink", "from_agent": "a", "to_agent": "*",
                       "signal_type": "handshake", "payload": {"summary": "broadcast"},
                       "delivered_at": None, "ts": "t1"}),
        ])
        mock_open = unittest.mock.mock_open(read_data=recall_text)
        with patch("builtins.open", mock_open):
            with patch("os.path.exists", return_value=True):
                winks = list_undelivered_winks(target_agent="junshi")
        self.assertEqual(len(winks), 1)
        self.assertEqual(winks[0]["payload"]["summary"], "broadcast")


if __name__ == "__main__":
    unittest.main(verbosity=2)
