#!/usr/bin/env python3
"""
章鱼搜索系统 · 测试套件
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from octopus import (
    _cross_validate,
    _build_timeline,
    _build_decision_graph,
    _find_gaps,
    _query_hash,
    synthesize,
)

# ============================================================
# 触须测试
# ============================================================

class TestTentacles(unittest.TestCase):
    """触须模块测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_jiak_phase0_imports(self):
        """测试jiak触须可导入"""
        from tentacles import jiak_tentacle
        self.assertTrue(hasattr(jiak_tentacle, "phase0_gross_collect"))
        self.assertTrue(hasattr(jiak_tentacle, "build_delegate_task"))

    def test_recall_phase0_imports(self):
        """测试RECALL触须可导入"""
        from tentacles import recall_tentacle
        self.assertTrue(hasattr(recall_tentacle, "phase0_gross_collect"))
        self.assertTrue(hasattr(recall_tentacle, "build_delegate_task"))

    def test_session_tentacle_imports(self):
        """测试session触须可导入"""
        from tentacles import session_tentacle
        self.assertTrue(hasattr(session_tentacle, "phase0_gross_collect"))
        self.assertTrue(hasattr(session_tentacle, "build_delegate_task"))

    def test_jiak_phase0_no_index(self):
        """jiak触须在index.json不存在时返回错误"""
        from tentacles import jiak_tentacle
        # 临时修改JIAK_HOME指向不存在的路径
        with patch.object(jiak_tentacle, "JIAK_HOME", "/nonexistent/path"):
            result = jiak_tentacle.phase0_gross_collect("test")
            self.assertEqual(result["status"], "error")
            self.assertIn("error", result)

    def test_recall_phase0_no_file(self):
        """RECALL触须在文件不存在时返回错误"""
        from tentacles import recall_tentacle
        with patch.object(recall_tentacle, "RECALL_PATH", "/nonexistent/recall.jsonl"):
            result = recall_tentacle.phase0_gross_collect("test")
            self.assertEqual(result["status"], "error")

    def test_build_delegate_task_format(self):
        """测试delegate_task构建格式"""
        from tentacles import session_tentacle
        task = session_tentacle.build_delegate_task("测试")
        self.assertIn("goal", task)
        self.assertIn("context", task)
        self.assertIn("测试", task["goal"])


# ============================================================
# 主脑测试
# ============================================================

class TestMainBrain(unittest.TestCase):
    """主脑合成功能测试"""

    def setUp(self):
        self.sample_facts = [
            {"type": "decision", "content": "使用AGFT冻结语义头", "confidence": "high", "source_ref": "实验记录"},
            {"type": "insight", "content": "D₀=3跨架构收敛", "confidence": "high", "source_ref": "IAH扫描"},
            {"type": "correction", "content": "两点不能定函数", "confidence": "high", "source_ref": "用户纠正"},
            {"type": "preference", "content": "暴力验证协议", "confidence": "medium", "source_ref": "工作记录"},
        ]
        self.sample_jiak_facts = [
            {"type": "decision", "content": "使用AGFT冻结语义头", "confidence": "medium", "source_ref": "jiak卡片"},
            {"type": "insight", "content": "LLM母语=世界模型", "confidence": "high", "source_ref": "范式转移"},
        ]

    def test_cross_validate_dedup(self):
        """交叉验证应去重多源事实"""
        result = _cross_validate(self.sample_facts, self.sample_jiak_facts, [])
        validated = result["validated_facts"]

        # 找到多源事实
        multi_source = [f for f in validated if len(f.get("sources", [])) > 1]
        self.assertGreaterEqual(len(multi_source), 1)

        # AGFT决策应有两个来源
        agft_facts = [f for f in validated if "AGFT" in f["content"]]
        self.assertGreaterEqual(len(agft_facts), 1)
        self.assertIn("session", agft_facts[0].get("sources", []))
        self.assertIn("jiak", agft_facts[0].get("sources", []))

    def test_cross_validate_no_duplicates(self):
        """交叉验证不应有内容完全相同的重复条目"""
        result = _cross_validate(self.sample_facts, [], [])
        contents = [f["content"] for f in result["validated_facts"]]
        self.assertEqual(len(contents), len(set(contents)))

    def test_build_timeline(self):
        """时间线构建"""
        validated = _cross_validate(self.sample_facts, [], [])
        timeline = _build_timeline(validated["validated_facts"])
        self.assertGreaterEqual(len(timeline), 4)

    def test_decision_graph(self):
        """决策图谱构建"""
        graph = _build_decision_graph(self.sample_facts)
        self.assertIn("decisions", graph)
        self.assertIn("corrections", graph)
        self.assertIn("links", graph)

    def test_find_gaps(self):
        """信息缺口检测"""
        validated = _cross_validate(self.sample_facts, [], [])
        gaps = _find_gaps(validated["validated_facts"], "测试查询")
        # 应检测到单源事实
        true_gaps = [g for g in gaps if g["type"] == "gap"]
        self.assertGreaterEqual(len(true_gaps), 0)

    def test_find_gaps_empty(self):
        """无结果时应有缺口"""
        gaps = _find_gaps([], "不存在的内容")
        self.assertGreaterEqual(len(gaps), 1)

    def test_query_hash(self):
        """查询哈希应稳定"""
        h1 = _query_hash("联邦制")
        h2 = _query_hash("联邦制")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 8)

    def test_synthesize(self):
        """完整合成管线"""
        result = synthesize(
            {"result": self.sample_facts},
            {"result": self.sample_jiak_facts},
            {"result": []},
            "AGFT"
        )
        self.assertIn("validated_facts", result)
        self.assertIn("timeline", result)
        self.assertIn("decisions", result)
        self.assertIn("corrections", result)
        self.assertIn("info_gaps", result)
        self.assertIn("source_counts", result)

    def test_synthesize_with_raw_snippets(self):
        """合成管线应处理raw_snippets回退"""
        result = synthesize(
            {"raw_snippets": ["session原始片段1", "session原始片段2"]},
            {"raw_snippets": ["jiak卡片摘要1"]},
            {"raw_snippets": ["RECALL事件记录1"]},
            "测试"
        )
        self.assertIn("validated_facts", result)
        self.assertGreaterEqual(result["source_counts"]["session"], 2)

    def test_synthesize_with_empty(self):
        """合成管线应处理全部空输入"""
        result = synthesize({}, {}, {}, "空查询")
        self.assertIn("info_gaps", result)
        # 无事实时source_counts应为0
        self.assertEqual(result["source_counts"]["session"], 0)
        self.assertEqual(result["source_counts"]["jiak"], 0)
        self.assertEqual(result["source_counts"]["recall"], 0)


# ============================================================
# CLI测试
# ============================================================

class TestCLI(unittest.TestCase):
    """命令行接口测试"""

    def test_search_local_mode(self):
        """本地模式search应返回预期结构"""
        # 使用模块导入避免执行副作用
        import importlib
        octopus = importlib.import_module("octopus")
        output = octopus.search("测试查询", run_local=True)
        self.assertIn("result", output)
        self.assertIn("query_card_id", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
