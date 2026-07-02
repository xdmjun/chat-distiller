# -*- coding: utf-8 -*-
"""
基础输出管理：将清洗结果写入 vault 目录结构
"""

import json
import os
import datetime
from pathlib import Path
from typing import List


def write_distilled_note(
    output_dir: Path,
    title: str,
    source: str,
    session_id: str,
    tags: List[str],
    score: float,
    category: str,
    concepts: List[str],
    cleaned_content: str,
) -> Path:
    """
    写入一篇蒸馏后的笔记到 vault/distilled/notes/

    返回输出文件路径
    """
    notes_dir = output_dir / 'distilled' / 'notes'
    notes_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名：日期_标题
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    filename = f"{today}_{safe_title}.md"
    out_path = notes_dir / filename

    # 构建 frontmatter
    safe_title_escaped = title.replace('"', "'")
    tags_json = json.dumps(tags, ensure_ascii=False)
    concepts_json = json.dumps(concepts, ensure_ascii=False)
    created = datetime.datetime.now().isoformat()

    frontmatter = (
        f'---\n'
        f'title: "{safe_title_escaped}"\n'
        f'source: "{source}"\n'
        f'session_id: "{session_id}"\n'
        f'tags: {tags_json}\n'
        f'score: {score}\n'
        f'category: "{category}"\n'
        f'concepts: {concepts_json}\n'
        f'created: {created}\n'
        f'---\n'
    )

    final_content = f"{frontmatter}\n# {title}\n\n{cleaned_content}"
    out_path.write_text(final_content, encoding='utf-8')
    return out_path


def write_raw_archive(output_dir: Path, source_rel: str, original_content: str):
    """归档原始对话到 vault/raw/"""
    raw_dir = output_dir / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / source_rel.replace('/', '_')
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(original_content, encoding='utf-8')


def write_stats(output_dir: Path, stats: dict):
    """写入 _stats.json 统计文件"""
    stats_path = output_dir / '_stats.json'
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


import re  # noqa: E402
