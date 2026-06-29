#!/usr/bin/env python3
"""
联邦注册表 · 测试套件
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import federal_registry


class TestFederalRegistry(unittest.TestCase):
    """联邦注册表核心功能测试"""

    def setUp(self):
        # 用临时文件替代注册表路径
        self.temp_registry = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.temp_registry.write(json.dumps({"mappings": [], "generated": ""}))
        self.temp_registry.close()
        self.reg_patcher = patch.object(federal_registry, "REGISTRY_PATH", self.temp_registry.name)
        self.reg_patcher.start()
        # mock recall_append
        self.recall_patcher = patch.object(federal_registry, "_recall_append", return_value=True)
        self.mock_recall = self.recall_patcher.start()

    def tearDown(self):
        self.reg_patcher.stop()
        self.recall_patcher.stop()
        os.unlink(self.temp_registry.name)

    def test_register_new(self):
        """注册新session应创建映射"""
        result = federal_registry.register("session_001", "executor")
        self.assertTrue(result)
        self.mock_recall.assert_called_once()
        call_args = self.mock_recall.call_args[0][0]
        self.assertEqual(call_args["type"], "federal_register")
        self.assertEqual(call_args["session_id"], "session_001")
        self.assertEqual(call_args["agent_id"], "executor")

    def test_register_update(self):
        """注册已存在的session应更新agent_id"""
        federal_registry.register("session_001", "executor")
        result = federal_registry.register("session_001", "junshi")
        self.assertTrue(result)
        mappings = federal_registry._read_registry().get("mappings", [])
        session_mappings = [m for m in mappings if m["session_id"] == "session_001"]
        self.assertEqual(len(session_mappings), 1)
        self.assertEqual(session_mappings[0]["agent_id"], "junshi")

    def test_register_multiple_sessions(self):
        """同一Agent可在多个session上"""
        federal_registry.register("session_001", "executor")
        federal_registry.register("session_002", "executor")
        mappings = federal_registry._read_registry().get("mappings", [])
        self.assertEqual(len(mappings), 2)

    def test_unregister(self):
        """注销应移除session但不删除agent_id的注册能力"""
        federal_registry.register("session_001", "executor")
        result = federal_registry.unregister("session_001")
        self.assertTrue(result)
        mappings = federal_registry._read_registry().get("mappings", [])
        self.assertEqual(len(mappings), 0)

    def test_unregister_nonexistent(self):
        """注销不存在的session应返回False"""
        result = federal_registry.unregister("nonexistent")
        self.assertFalse(result)

    def test_lookup(self):
        """查agent_id应返回所有活跃session"""
        federal_registry.register("session_001", "executor")
        federal_registry.register("session_002", "executor")
        federal_registry.register("session_003", "junshi")
        results = federal_registry.lookup("executor")
        self.assertEqual(len(results), 2)
        session_ids = {r["session_id"] for r in results}
        self.assertEqual(session_ids, {"session_001", "session_002"})

    def test_lookup_empty(self):
        """查不存在的agent_id应返回空列表"""
        results = federal_registry.lookup("nobody")
        self.assertEqual(results, [])

    def test_lookup_session(self):
        """反向查找session_id"""
        federal_registry.register("session_001", "executor")
        result = federal_registry.lookup_session("session_001")
        self.assertIsNotNone(result)
        self.assertEqual(result["agent_id"], "executor")

    def test_lookup_session_empty(self):
        """反向查找不存在的session_id"""
        result = federal_registry.lookup_session("nonexistent")
        self.assertIsNone(result)

    def test_list_active_agents(self):
        """列出所有活跃Agent（去重）"""
        federal_registry.register("s1", "executor")
        federal_registry.register("s2", "executor")
        federal_registry.register("s3", "junshi")
        agents = federal_registry.list_active_agents()
        self.assertEqual(set(agents), {"executor", "junshi"})

    def test_list_active_sessions(self):
        """列出活跃session"""
        federal_registry.register("s1", "executor")
        federal_registry.register("s2", "junshi")
        sessions = federal_registry.list_active_sessions("executor")
        self.assertEqual(sessions, ["s1"])

    def test_persistence(self):
        """注册表应在多次读取间持久化"""
        federal_registry.register("session_001", "executor")
        # 重新读取注册表
        registry = federal_registry._read_registry()
        self.assertEqual(len(registry["mappings"]), 1)
        self.assertEqual(registry["mappings"][0]["agent_id"], "executor")

    def test_recall_trail(self):
        """注册和注销都走RECALL审计"""
        federal_registry.register("session_001", "executor")
        self.assertEqual(self.mock_recall.call_count, 1)
        federal_registry.unregister("session_001")
        self.assertEqual(self.mock_recall.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
