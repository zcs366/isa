#!/usr/bin/env python3
"""
Brain v0.2 单元测试
===================
🔨赫淮斯托斯: 覆盖信号摄入、分词、检索、洞察写入、补偿重试、Dreaming、健康检查
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 确保可以从isa项目导入
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import Brain


class TestBrainKeywords(unittest.TestCase):
    """🦉雅典娜: 分词测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_text(self):
        self.assertEqual(self.brain._extract_keywords(""), [])
        self.assertEqual(self.brain._extract_keywords("   "), [])

    def test_chinese_segmentation(self):
        """jieba中文分词：语义共振通信平台 → 多个词"""
        words = self.brain._extract_keywords("语义共振通信平台")
        self.assertTrue(len(words) >= 2, f"分词失败: {words}")

    def test_stopwords_filtered(self):
        words = self.brain._extract_keywords("我的你的他的它们的这是那是在和与或吗呢吧")
        self.assertEqual(words, [], f"停用词未过滤: {words}")

    def test_mixed_cn_en(self):
        """中英混合: ISA波扩散机制和jika记忆检索"""
        words = self.brain._extract_keywords("ISA波扩散机制和jika记忆检索")
        self.assertTrue(any("ISA" in w for w in words), f"ISA未识别: {words}")
        self.assertTrue(any("jika" in w for w in words), f"jika未识别: {words}")

    def test_punctuation_only(self):
        words = self.brain._extract_keywords("，。！？；：""''")
        self.assertEqual(words, [])

    def test_long_text_capped(self):
        """超长文本也只返回最多10个关键词"""
        long_text = " ".join([f"关键词{i}" for i in range(50)])
        words = self.brain._extract_keywords(long_text)
        self.assertLessEqual(len(words), 10)


class TestBrainSearch(unittest.TestCase):
    """检索测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))
        # 预写测试卡片
        self.brain._write_card("isa-wave", {
            "card_id": "isa-wave", "title": "ISA波扩散",
            "keywords": ["ISA", "波扩散", "语义距离", "Jaccard"],
            "summary": "波扩散机制", "status": "active",
            "decisions": [], "notes": [],
        })
        self.brain._write_card("jika-engine", {
            "card_id": "jika-engine", "title": "jika引擎",
            "keywords": ["jika", "记忆", "检索", "BM25"],
            "summary": "记忆引擎", "status": "active",
            "decisions": [], "notes": [],
        })

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_keyword_match(self):
        matched = self.brain._search(["ISA", "波扩散"])
        self.assertTrue(any(m["card_id"] == "isa-wave" for m in matched))

    def test_no_match(self):
        matched = self.brain._search(["不存在的词"])
        self.assertEqual(matched, [])

    def test_partial_match(self):
        matched = self.brain._search(["jika", "记忆"])
        self.assertTrue(any(m["card_id"] == "jika-engine" for m in matched))

    def test_score_ordering(self):
        self.brain._write_card("both", {
            "card_id": "both", "title": "两者都涉及",
            "keywords": ["ISA", "jika", "统一", "架构"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        matched = self.brain._search(["ISA", "jika"])
        self.assertGreaterEqual(len(matched), 2)
        # "both" 命中两个关键词应该排第一
        self.assertEqual(matched[0]["card_id"], "both")


class TestBrainInsight(unittest.TestCase):
    """洞察写入+RECALL追加测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_insight_write(self):
        self.brain.insight("test-card", "这是一个测试洞察")
        card = self.brain._read_card("test-card")
        self.assertTrue(len(card.get("notes", [])) > 0)
        self.assertIn("测试洞察", card["notes"][0]["content"])

    def test_insight_appends_recall(self):
        self.brain.insight("test-card", "RECALL测试")
        recall = self.brain.recall_path.read_text()
        self.assertIn("RECALL测试", recall)

    def test_new_card_autocreate(self):
        self.brain.insight("new-card", "自动创建的卡片")
        card = self.brain._read_card("new-card")
        self.assertEqual(card["card_id"], "new-card")

    def test_session_insights(self):
        self.brain.insight("c1", "洞察1", emit=False)
        self.brain.insight("c2", "洞察2", emit=False)
        self.assertEqual(len(self.brain.new_insights), 2)

    def test_emit_callback(self):
        emitted = []
        brain = Brain("test", brain_dir=Path(tempfile.mkdtemp()),
                      on_new_insight=lambda cid, content: emitted.append((cid, content)))
        brain.insight("x", "测试扩散")
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0][0], "x")


class TestBrainCompensation(unittest.TestCase):
    """⚔️阿瑞斯: 补偿机制测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stats_initial(self):
        s = self.brain.stats
        self.assertEqual(s["signals_ingested"], 0)
        self.assertEqual(s["write_failures"], 0)

    def test_signal_stats_increment(self):
        self.brain.ingest_signal({"body": "测试信号", "source": "test"})
        self.assertEqual(self.brain.stats["signals_ingested"], 1)


class TestBrainDreaming(unittest.TestCase):
    """☀️阿波罗: Dreaming关联测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_cards(self):
        discoveries = self.brain.dream()
        self.assertEqual(discoveries, [])

    def test_overlap_detection(self):
        self.brain._write_card("c1", {
            "card_id": "c1", "title": "C1",
            "keywords": ["ISA", "波扩散", "语义"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        self.brain._write_card("c2", {
            "card_id": "c2", "title": "C2",
            "keywords": ["ISA", "波扩散", "通信"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        discoveries = self.brain.dream()
        self.assertGreaterEqual(len(discoveries), 1)
        self.assertIn("ISA", discoveries[0]["shared_keywords"])

    def test_no_overlap(self):
        self.brain._write_card("c1", {
            "card_id": "c1", "title": "C1",
            "keywords": ["x", "y", "z"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        self.brain._write_card("c2", {
            "card_id": "c2", "title": "C2",
            "keywords": ["a", "b", "c"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        discoveries = self.brain.dream()
        self.assertEqual(discoveries, [])


class TestBrainHealth(unittest.TestCase):
    """🔨赫淮斯托斯: 健康检查"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_health_initial(self):
        h = self.brain.health()
        self.assertTrue(h["ok"])
        self.assertEqual(h["pending_writes"], 0)
        self.assertEqual(h["card_count"], 0)

    def test_health_with_cards(self):
        self.brain.insight("c1", "insight", emit=False)
        h = self.brain.health()
        self.assertEqual(h["card_count"], 1)


class TestBrainPredict(unittest.TestCase):
    """⏳克洛诺斯: 预测器测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))
        self.brain._write_card("isa", {
            "card_id": "isa", "title": "ISA通信",
            "keywords": ["ISA", "通信", "Gateway"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        self.brain._write_card("jika", {
            "card_id": "jika", "title": "jika记忆",
            "keywords": ["jika", "记忆", "检索"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })
        self.brain._write_card("unified", {
            "card_id": "unified", "title": "ISA+jika统一",
            "keywords": ["ISA", "jika", "统一", "架构"],
            "summary": "", "status": "active",
            "decisions": [], "notes": [],
        })

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_direct_prediction(self):
        preds = self.brain.predict("ISA通信协议")
        self.assertTrue(any(p["card_id"] == "isa" for p in preds))

    def test_association_prediction(self):
        preds = self.brain.predict("jika记忆引擎")
        # "jika" matches "jika" card, dream associates "jika" with "unified"
        self.assertTrue(any(p["card_id"] == "jika" for p in preds))

    def test_confidence_bounded(self):
        preds = self.brain.predict("ISA通信")
        for p in preds:
            self.assertGreaterEqual(p["confidence"], 0.0)
            self.assertLessEqual(p["confidence"], 1.0)


class TestBrainRecognize(unittest.TestCase):
    """💎阿佛洛狄忒: 仪式感测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.brain = Brain("test", brain_dir=Path(self.tmp))
        # 手动建卡设关键词（insight自建卡无关键词）
        self.brain._write_card("isa-wave", {
            "card_id": "isa-wave", "title": "ISA波扩散",
            "keywords": ["波扩散", "ISA", "语义距离", "Jaccard"],
            "summary": "波扩散机制", "status": "active",
            "decisions": [], "notes": [
                {"date": "2026-06-20", "content": "波扩散是语义选通在空间维的实现"},
                {"date": "2026-06-20", "content": "Jaccard距离决定消息传播范围"},
                {"date": "2026-06-20", "content": "三端统一验证了层间解耦"},
            ],
        })

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recognize_strong_match(self):
        result = self.brain.recognize("波扩散机制如何工作")
        self.assertIsNotNone(result)
        self.assertIn("ISA波扩散", result)
        self.assertIn("三端统一", result)

    def test_recognize_no_match(self):
        result = self.brain.recognize("完全无关的话题")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
