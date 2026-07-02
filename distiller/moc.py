# -*- coding: utf-8 -*-
"""
MOC 生成器（--ob-wiki 模式）：概念卡片 + 索引页 + CLAUDE.md + links.json
"""

import json
import datetime
from pathlib import Path
from typing import List, Dict


def write_concept_cards(
    output_dir: Path,
    concept_notes: Dict[str, List[str]],
):
    """
    为每个概念生成概念卡片文件 distilled/concepts/<concept>.md
    concept_notes: { concept_name: [note_title, ...] }
    """
    concepts_dir = output_dir / 'distilled' / 'concepts'
    concepts_dir.mkdir(parents=True, exist_ok=True)

    for concept, notes in concept_notes.items():
        safe_name = concept.replace('/', '_').replace(':', '_')
        card_path = concepts_dir / f'{safe_name}.md'

        # 构建反向链接
        backlinks = '\n'.join(f'- [[{note}]]' for note in notes)

        content = (
            f'---\n'
            f'concept: "{concept}"\n'
            f'type: "concept-card"\n'
            f'linked_notes: {json.dumps(notes, ensure_ascii=False)}\n'
            f'created: {datetime.datetime.now().isoformat()}\n'
            f'---\n'
            f'\n# {concept}\n\n'
            f'## 关联笔记\n\n{backlinks}\n'
        )
        card_path.write_text(content, encoding='utf-8')


def write_moc(output_dir: Path, all_notes: List[Dict]):
    """
    生成 MOC 索引页 distilled/moc/README.md
    """
    moc_dir = output_dir / 'distilled' / 'moc'
    moc_dir.mkdir(parents=True, exist_ok=True)

    moc_path = moc_dir / 'README.md'

    high = [n for n in all_notes if n.get('category') == 'high']
    medium = [n for n in all_notes if n.get('category') == 'medium']
    low = [n for n in all_notes if n.get('category') == 'low']

    def note_line(n):
        concepts_str = ', '.join(f'[[{c}]]' for c in n.get('concepts', []))
        return f'- [[{n["title"]}]] — score: {n["score"]} {concepts_str}'

    lines = [
        '---',
        'type: "moc"',
        f'created: {datetime.datetime.now().isoformat()}',
        '---',
        '',
        '# 对话蒸馏索引',
        '',
        f'总计: {len(all_notes)} 篇笔记',
        '',
        '## 高价值 (score ≥ 6.0)',
        '',
    ]
    for n in high:
        lines.append(note_line(n))
    lines.extend([
        '',
        '## 中等价值 (score 3.5–5.9)',
        '',
    ])
    for n in medium:
        lines.append(note_line(n))
    lines.extend([
        '',
        '## 低价值 (score 2.0–3.4)',
        '',
    ])
    for n in low:
        lines.append(note_line(n))

    moc_path.write_text('\n'.join(lines), encoding='utf-8')


def write_links_json(output_dir: Path, links_index: Dict[str, List[str]]):
    """
    生成 _index/links.json 反向链接索引
    links_index: { concept: [note_title, ...] }
    """
    index_dir = output_dir / '_index'
    index_dir.mkdir(parents=True, exist_ok=True)
    links_path = index_dir / 'links.json'
    links_path.write_text(
        json.dumps(links_index, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def write_claude_md(output_dir: Path, wiki_path: str = "./wiki"):
    """
    生成 .claude/CLAUDE.md vault 结构说明
    """
    claude_dir = output_dir / '.claude'
    claude_dir.mkdir(parents=True, exist_ok=True)
    claude_path = claude_dir / 'CLAUDE.md'

    content = (
        f'# Chat Distiller — 对话清洗结果\n'
        f'\n'
        f'## vault 结构\n'
        f'- `distilled/notes/` — 已清洗的对话笔记（`--ob-wiki` 模式含双链）\n'
        f'- `distilled/concepts/` — 概念卡片（仅 `--ob-wiki`）\n'
        f'- `distilled/moc/` — 索引页（仅 `--ob-wiki`）\n'
        f'- `_index/links.json` — 反向链接索引\n'
        f'- `manifest.json` — 增量追踪\n'
        f'\n'
        f'## 评分系统（0-15）\n'
        f'- score ≥ 6 (high)  → 优先摄入 wiki\n'
        f'- score 3.5–5.9 (medium) → 可摄入但非优先\n'
        f'- score 2.0–3.4 (low) → 已过滤，不建议摄入\n'
        f'- score < 2.0 → 已丢弃，不存在于此 vault\n'
        f'\n'
        f'## 推荐工作流\n'
        f'- 批量摄入高分笔记：`/wiki-ingest distilled/notes/`（AI agent 会优先选择 score ≥ 6 的文件）\n'
        f'- 单篇摄入：`/wiki-ingest distilled/notes/<file>.md`\n'
        f'- 复核低分笔记：查看 score < 6 的文件，决定是否保留\n'
    )
    claude_path.write_text(content, encoding='utf-8')
