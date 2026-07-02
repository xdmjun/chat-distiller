# Chat Distiller

> AI 对话的前置清洗器。将各种格式的 AI 对话导出清洗为干净、评分过的 Markdown，作为 **wiki-ingest 的前置步骤**，确保低价值知识不会混入 wiki。

## 快速开始

```bash
pip install -r requirements.txt

# 基础清洗
python scripts/distill.py --source ./raw --output ./vault

# 清洗 + Obsidian 格式（双链 + 概念卡片 + MOC）
python scripts/distill.py --source ./raw --output ./vault --ob-wiki

# 质量控制
python scripts/verify.py --dir ./vault
```

## 核心能力

| 能力 | 说明 |
|------|------|
| **多格式输入** | Agent .md / ChatGPT JSON / Claude JSONL / 通用文本 / 纯文本 |
| **规则清洗** | 200+ 中文套话 + 50+ 英文套话正则过滤 |
| **6 维评分** | 信息密度 / 技术深度 / 白名单 / 关键词 / 长度惩罚 / 套话惩罚（0-15 分） |
| **概念抽取** | jieba 分词 + 词频统计 + 同义归一 |
| **增量处理** | manifest.json MD5 去重 |
| **--ob-wiki 模式** | [[wikilink]] 双链 / 概念卡片 / MOC / CLAUDE.md / links.json |
| **配置热加载** | 运行时检测 config.yaml 变更自动重载 |

## 架构

```
chat-distiller/
├── distiller/          ← Python 核心包
│   ├── adapter.py      ← 多格式输入解析器
│   ├── cleaner.py      ← 规则清洗引擎
│   ├── scorer.py       ← 6 维评分引擎
│   ├── concepts.py     ← 概念抽取（jieba）
│   ├── renderer.py     ← [[wikilink]] 双链渲染
│   ├── moc.py          ← MOC / 概念卡片 / CLAUDE.md 生成
│   ├── output.py       ← vault 输出管理
│   ├── config.py       ← 配置管理 + 热加载
│   └── utils.py        ← 工具函数 + manifest 增量追踪
├── scripts/
│   ├── distill.py      ← CLI 主入口
│   └── verify.py       ← 质量验证脚本
├── config.yaml         ← 套话库 + 白名单 + 评分阈值
└── requirements.txt    ← PyYAML + click + jieba（零外部 API）
```

## 评分阈值

| 分级 | 分数 | 处理 |
|------|------|------|
| high | ≥ 6.0 | 优先推荐给 wiki-ingest |
| medium | 3.5–5.9 | 保留但不优先 |
| low | 2.0–3.4 | 已过滤 |
| skip | < 2.0 | 直接丢弃 |

## License

AGPL-3.0
