#!/usr/bin/env python3
"""
ISA信号接收器+Dreaming扩展 测试
=================================
Step 1: skill_created信号接收器
Step 2: dream_insight信号发送器
Step 3: DreamBridge扩展
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from skill_signal_receiver import (
    process_skill_received,
    append_to_e_layer,
    append_to_brain_dream,
)
from dream_insight_sender import (
    format_dream_insight,
    send_dream_insight,
)


class TestSkillSignalReceiver(unittest.TestCase):
    """Step 1: skill_created信号接收器"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.brain_dir = Path(self.tmpdir) / "brain" / "test-agent"
        self.brain_dir.mkdir(parents=True, exist_ok=True)

    def test_process_skill_received_writes_three_targets(self):
        """skill_created信号写入Δ胶囊E层+brain_dream+RECALL"""
        signal = {
            "type": "skill_created",
            "from": "isn",
            "payload": {
                "name": "test-skill-001",
                "description": "A test skill",
                "category": "devops",
                "keywords": ["test", "skill", "devops"],
            }
        }
        with patch("skill_signal_receiver.DELTA_E_LAYER",
                    Path(self.tmpdir) / "e_layer.jsonl"), \
             patch("skill_signal_receiver.BRAIN_DIR", Path(self.tmpdir) / "brain"), \
             patch("skill_signal_receiver._sys_recall_append", return_value=True):
            result = process_skill_received(signal, "test-agent")

        self.assertTrue(result["ok"])
        self.assertEqual(result["skill_name"], "test-skill-001")
        self.assertTrue(result["writes"]["e_layer"])
        self.assertTrue(result["writes"]["brain_dream"])
        self.assertTrue(result["writes"]["recall"])

    def test_e_layer_write(self):
        """Δ胶囊E层写入正确JSONL格式"""
        e_path = Path(self.tmpdir) / "e_layer.jsonl"
        event = {"type": "skill_created", "source": "isn", "timestamp": "2026-01-01T00:00:00Z",
                 "_written_by": "isa"}
        with patch("skill_signal_receiver.DELTA_E_LAYER", e_path):
            ok = append_to_e_layer(event)
        self.assertTrue(ok)
        content = e_path.read_text().strip()
        parsed = json.loads(content)
        self.assertEqual(parsed["type"], "skill_created")
        self.assertEqual(parsed["_written_by"], "isa")

    def test_brain_dream_write(self):
        """brain_dream.jsonl写入正确格式"""
        entry = {
            "type": "skill_created",
            "skill_name": "my-skill",
            "keywords": ["a", "b"],
        }
        with patch("skill_signal_receiver.BRAIN_DIR", Path(self.tmpdir) / "brain"):
            ok = append_to_brain_dream("test-agent", entry)
        self.assertTrue(ok)
        dream_path = Path(self.tmpdir) / "brain" / "test-agent" / "brain_dream.jsonl"
        content = dream_path.read_text().strip()
        parsed = json.loads(content)
        self.assertEqual(parsed["type"], "skill_created")
        self.assertEqual(parsed["skill_name"], "my-skill")


class TestDreamInsightSender(unittest.TestCase):
    """Step 2: dream_insight信号发送器"""

    def test_format_dream_insight(self):
        """格式化dream_insight信号"""
        discovery = {
            "card_a": "isa-wave-mechanics",
            "card_b": "brain-dreaming",
            "shared_keywords": ["ISA", "语义"],
            "source": "keyword",
        }
        envelope = format_dream_insight(discovery, "test-agent")
        self.assertEqual(envelope["type"], "dream_insight")
        self.assertEqual(envelope["from"], "test-agent")
        self.assertEqual(envelope["to"], "isn")
        self.assertIn("insight", envelope["payload"])
        self.assertIn("suggested_action", envelope["payload"])
        self.assertEqual(envelope["payload"]["card_a"], "isa-wave-mechanics")
        self.assertEqual(envelope["payload"]["card_b"], "brain-dreaming")

    def test_suggested_action_values(self):
        """suggested_action在四种合法值内"""
        discovery = {
            "card_a": "a", "card_b": "b",
            "shared_keywords": ["x"], "source": "keyword",
        }
        envelope = format_dream_insight(discovery)
        valid_actions = {"create", "update", "merge", "retire"}
        self.assertIn(envelope["payload"]["suggested_action"], valid_actions)

    def test_recall_entry_format(self):
        """RECALL条目有_written_by签名"""
        discovery = {
            "card_a": "a", "card_b": "b",
            "shared_keywords": ["x"], "source": "keyword",
        }
        with patch("dream_insight_sender._sys_signal_send", return_value="sig-001"), \
             patch("dream_insight_sender._sys_recall_append", return_value=True) as mock_recall:
            send_dream_insight(discovery, "test-agent")
            # 检查recall_append调用
            call_args = mock_recall.call_args[0][0]
            self.assertEqual(call_args["_written_by"], "isa")
            self.assertEqual(call_args["type"], "dream_insight_sent")


class TestDreamBridgeExtension(unittest.TestCase):
    """Step 3: DreamBridge扩展"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.brain_dir = Path(self.tmpdir) / "brain" / "test-agent"
        self.brain_dir.mkdir(parents=True, exist_ok=True)

    def test_process_skill_created_events_empty(self):
        """空brain_dream.jsonl返回空列表"""
        from brain import Brain
        with patch.object(Brain, '__init__', lambda self, *a, **kw: None):
            b = Brain.__new__(Brain)
            b.brain_dir = self.brain_dir
            b.agent_id = "test-agent"
            result = b.process_skill_created_events()
        self.assertEqual(result, [])

    def test_process_skill_created_events_with_event(self):
        """处理skill_created事件"""
        from brain import Brain

        # 写入一个skill_created事件
        dream_log = self.brain_dir / "brain_dream.jsonl"
        event = {
            "type": "skill_created",
            "skill_name": "new-skill",
            "skill_desc": "desc",
            "keywords": ["ISA", "语义"],
            "timestamp": "2026-01-01T00:00:00Z",
        }
        with open(dream_log, "w") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        # 创建Brain实例
        cards_dir = self.brain_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.brain_dir / "index.json"
        index_path.write_text(json.dumps({"cards": {
            "card-a": {"keywords": ["ISA", "波扩散"]},
            "card-b": {"keywords": ["语义", "记忆"]},
        }}, ensure_ascii=False))

        with patch.object(Brain, '__init__', lambda self, *a, **kw: None):
            b = Brain.__new__(Brain)
            b.brain_dir = self.brain_dir
            b.cards_dir = cards_dir
            b.index_path = index_path
            b.agent_id = "test-agent"
            b._session_insights = []
            b._stats = {}
            b._read_json = lambda p: json.loads(p.read_text()) if Path(p).exists() else {}
            b._read_card = lambda cid: json.loads((cards_dir / f"{cid}.json").read_text()) if (cards_dir / f"{cid}.json").exists() else {}
            b._extract_keywords = lambda text: [w for w in text.split() if len(w) >= 2]
            b._forward_traverse = lambda cues, max_depth=3: []
            b._backward_traverse = lambda cid, max_new=5: []

            with patch("dream_insight_sender.send_dream_insight", return_value={"ok": True}):
                result = b.process_skill_created_events()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["skill_name"], "new-skill")


if __name__ == "__main__":
    unittest.main(verbosity=2)
