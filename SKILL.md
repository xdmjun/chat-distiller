---
name: "chat-distiller"
description: "将 AI 对话导出（.md/.json/.jsonl）清洗为干净的、评分过的 Markdown 笔记，作为 wiki-ingest 的前置步骤。支持多格式输入、200+ 套话过滤、6 维评分、--ob-wiki 模式。"
---

# Chat Distiller - 对话蒸馏工具

将各种格式的 AI 对话导出清洗为干净、评分过的 Markdown，作为 **wiki-ingest 的前置步骤**，确保低价值知识不会混入 wiki。

## 使用方式

```bash
# 基础清洗
python scripts/distill.py --source ./raw --output ./vault

# 清洗 + Obsidian 格式（双链 + 概念卡片 + MOC）
python scripts/distill.py --source ./raw --output ./vault --ob-wiki

# 仅评分预览（不输出文件）
python scripts/distill.py --source ./raw --dry-run

# 质量控制
python scripts/verify.py --dir ./vault
```

## 核心流程

```
原始对话（含大量 AI 套话） → chat-distiller（规则引擎）
  ├─ ① parse_dialogue()     → 多格式解析
  ├─ ② clean_200plus()      → 200+ 正则去套话
  ├─ ③ score_6dim()         → 0-15 评分
  ├─ ④ extract_concepts()   → jieba 概念抽取
  └─ ⑤ manifest_sync()      → 增量追踪

产出 → distilled/notes/*.md（干净、评分过、概念标注）
     → manifest.json（增量清单）
     → --ob-wiki 额外产出: concepts/*.md, moc/*.md, CLAUDE.md
```

## 评分系统（0-15）

| 分级 | 分数 | 处理 |
|------|------|------|
| high | ≥ 6.0 | 干净笔记 → wiki-ingest 候选 |
| medium | 3.5–5.9 | 保留但不优先 |
| low | 2.0–3.4 | 已过滤，不建议摄入 |
| skip | < 2.0 | 直接丢弃 |

## 与 wiki-ingest 的关系

chat-distiller 是 wiki-ingest 的上游。chat-distiller 负责"去噪音 + 打分"，wiki-ingest 负责"提取知识 + 写 wiki 页面"。两者是流水线关系。
