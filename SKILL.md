---
name: "chat-distiller"
description: "将 AI 对话导出的 MD 文件蒸馏为结构化知识页面。支持增量处理、动态白名单、项目合并、深度提取。当用户要求清洗/蒸馏对话导出文件、或需要处理新增的对话文件时调用。"
---

# Chat Distiller - 对话蒸馏技能

将 AI 对话导出的 MD 文件蒸馏为结构化 wiki 知识页面，去除对话噪音，保留核心知识。适用于任何导出为 MD 格式的 AI 对话记录（Claude、ChatGPT、Trae 等）。

## 核心特性

- **配置化白名单**: 规则存储在 `config.yaml`，无需修改代码
- **增量处理**: 只处理新增/变化的文件，跳过已处理的
- **项目合并**: 支持将多个目录合并为同一项目
- **质量评分**: 多维度评分 + 白名单机制
- **深度提取**: 利用 AI IDE 会话能力提取结构化知识（决策、行动项、概念等）

## 使用方法

### 首次全量蒸馏

```bash
python scripts/distill.py --source <源目录> --output <输出目录> --config config.yaml
```

### 增量蒸馏（只处理新增文件）

```bash
python distill.py --source <源目录> --output <输出目录> --config config.yaml --incremental
```

### 仅评分（不蒸馏）

```bash
python scripts/distill.py --source <源目录> --score-only --config config.yaml
```

### 验证质量

```bash
python verify.py --dir <蒸馏输出目录>
```

### 深度提取（AI 会话模式）

在 AI IDE 会话中直接调用，无需本地 LLM：

```
深度提取 <文件路径或目录>
```

或英文触发词：

```
extract <file_or_dir>
```

**输出目录结构**（与原文件所在目录同级）：

```
父目录/
├── 源目录/                        # 原文件目录
│   ├── conversation1.md
│   └── conversation2.md
└── 源目录_extracted/              # 输出目录（同级新建）
    ├── json/                      # JSON 结构化数据
    │   ├── conversation1.json
    │   └── conversation2.json
    └── md/                        # Markdown 可读版本
        ├── conversation1.md
        └── conversation2.md
```

**JSON 输出格式**：

```json
{
  "source": "conversation1.md",
  "timestamp": "2026-06-20T10:00:00",
  "title": "对话标题",
  "summary": "对话核心要点总结",
  "knowledge": {
    "decisions": [
      {
        "what": "选择 PostgreSQL 而非 MySQL",
        "why": "需要 JSONB 支持和全文搜索",
        "impact": "提升查询灵活性"
      }
    ],
    "ideas": [
      {
        "concept": "引入缓存层优化查询",
        "feasibility": "高",
        "value": "减少数据库压力"
      }
    ],
    "questions": [
      {
        "question": "如何处理并发写入冲突？",
        "context": "多用户同时编辑同一记录",
        "status": "open"
      }
    ],
    "action_items": [
      {
        "task": "实现用户认证模块",
        "owner": "后端",
        "deadline": "周五",
        "priority": "high"
      }
    ],
    "concepts": [
      {
        "name": "DDD 领域驱动设计",
        "definition": "以业务领域为核心的软件设计方法",
        "related": ["聚合根", "值对象", "领域事件"]
      }
    ],
    "terms": [
      {
        "term": "CQRS",
        "full_name": "Command Query Responsibility Segregation",
        "meaning": "命令查询职责分离模式"
      }
    ],
    "lessons": [
      {
        "situation": "在循环中执行数据库查询",
        "learning": "导致 N+1 查询问题",
        "apply_to": "使用批量查询或预加载"
      }
    ],
    "architecture": [
      {
        "component": "API 网关",
        "decision": "使用 Kong 作为统一入口",
        "alternatives": ["Nginx", "Traefik"],
        "rationale": "支持插件生态和动态路由"
      }
    ]
  }
}
```

## 配置文件说明

配置文件 `config.yaml` 包含以下部分：

### 1. 白名单规则 (whitelist_rules)

定义内容特征评分规则，每条规则包含：
- `name`: 规则名称
- `patterns`: 正则表达式列表
- `match_type`: `any`（匹配任一）或 `all`（匹配全部）
- `score`: 匹配时加的分数
- `max_score`: 该规则的最大贡献分数

### 2. 高价值关键词 (high_value_keywords)

用于标题和内容匹配的关键词列表。

### 3. 低价值关键词 (low_value_keywords)

用于惩罚的低价值关键词列表。

### 4. 排除文件名模式 (exclude_patterns)

需要排除的文件名正则表达式。

### 5. 操作性语句模式 (operational_patterns)

需要从内容中移除的 AI 过渡语句。

### 6. 项目合并 (project_merge)

将多个源目录合并为同一项目的映射。

### 7. 输出设置 (output)

- `min_content_lines`: 最少内容行数
- `min_content_chars`: 最少内容字符数
- `max_tags`: 最大标签数

## 增量处理机制

1. 首次运行时生成 `manifest.json`，记录已处理文件的 MD5 哈希
2. 后续运行时对比哈希，只处理新增/变化的文件
3. 使用 `--force` 参数可强制重新处理所有文件

## 输出格式

每个蒸馏后的文件包含：
```yaml
---
title: "标题"
project: "项目名"
source: "源文件路径"
tags: ["标签1", "标签2"]
score: 8.5
category: "high"
---

# 标题

（蒸馏后的知识内容）
```

## 分类结果

`_distill-result.json` 包含所有文件的分类信息：
```json
{
  "stats": {
    "total_input": 1764,
    "distilled": 1694,
    "too_short": 39,
    "too_few_lines": 31
  },
  "files": [
    {
      "path": "project/file.md",
      "title": "标题",
      "project": "项目名",
      "tags": ["标签"],
      "score": 8.5,
      "category": "high"
    }
  ]
}
```

## 示例

### 添加新的白名单规则

编辑 `config.yaml`，在 `whitelist_rules` 中添加：

```yaml
whitelist_rules:
  - name: "api_design"
    description: "API 设计相关内容"
    patterns:
      - "(?:REST|GraphQL|gRPC|API).*设计"
      - "(?:接口|端点|endpoint).*设计"
    match_type: "any"
    score: 1.5
    max_score: 2
```

### 添加项目合并

```yaml
project_merge:
  doc: liangxi        # doc 目录合并到 liangxi
  frontend: web-app   # frontend 目录合并到 web-app
```

## 深度提取模式详解

### 工作原理

深度提取利用 AI IDE（Trae、Cursor、Claude Code、Codex 等）会话中已有的模型能力，在对话过程中直接进行结构化知识提取，无需额外部署本地 LLM。

### 触发方式

在 AI IDE 会话中输入以下任一指令：

```
深度提取 <文件路径>
深度提取 <目录路径>
extract <file_or_dir>
```

### 处理流程

1. **读取对话文件**：支持 MD、JSONL、TXT 格式
2. **识别对话结构**：解析 User/Assistant 对话轮次
3. **提取结构化知识**：使用当前会话的模型能力分析内容
4. **输出结果**：
   - JSON 文件：结构化数据，便于程序处理
   - MD 文件：人类可读版本，便于浏览

### 输出目录结构

输出到原文件所在目录的**同级**目录，目录名为 `原目录名_extracted`，JSON 和 MD 分开存放：

```
父目录/
├── 源目录/                        # 原文件目录
│   ├── file1.md
│   └── file2.md
└── 源目录_extracted/              # 输出目录（同级新建）
    ├── json/
    │   ├── file1.json
    │   └── file2.json
    ├── md/
    │   ├── file1.md
    │   └── file2.md
    └── manifest.json              # 增量处理记录
```

### 提取的知识类别

| 类别 | 说明 | 示例 |
|------|------|------|
| `decisions` | 决策及原因 | 选择 X 而非 Y，因为... |
| `ideas` | 想法和建议 | 可以引入缓存优化... |
| `questions` | 待解决问题 | 如何处理并发冲突？ |
| `action_items` | 行动项 | 实现认证模块（负责人：后端） |
| `concepts` | 关键概念 | DDD 领域驱动设计 |
| `terms` | 术语缩写 | CQRS = Command Query Responsibility Segregation |
| `lessons` | 经验教训 | 避免在循环中执行数据库查询 |
| `architecture` | 架构决策 | 使用 Kong 作为 API 网关 |

### 与基础蒸馏的区别

| 特性 | 基础蒸馏 | 深度提取 |
|------|----------|----------|
| 实现方式 | 正则规则 + 配置 | AI 模型语义理解 |
| 处理速度 | 快 | 较慢（需要模型推理） |
| 提取粒度 | 整体清洗 | 8 类结构化知识 |
| 输出格式 | wiki 页面 | JSON + MD |
| 部署要求 | 无外部依赖 | 需要 AI IDE 会话 |
| 适用场景 | 批量处理大量文件 | 深度分析高价值对话 |

### 最佳实践

1. **先蒸馏后提取**：使用基础蒸馏筛选高价值文件（score >= 6），再对高价值文件进行深度提取
2. **增量处理**：记录已提取的文件，避免重复处理
3. **批量处理**：对目录中的所有文件进行深度提取时，逐文件处理并输出进度

### 增量深度提取

使用 `--incremental` 参数只处理新增/变化的文件：

```
深度提取 <目录> --incremental
```

已处理的文件记录在 `_extracted/manifest.json` 中。
