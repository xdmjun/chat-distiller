# -*- coding: utf-8 -*-
"""
双链渲染器（--ob-wiki 模式）：概念关键词 → [[wikilink]] 双链
"""

import re
from typing import List


def render_wikilinks(content: str, concepts: List[str]) -> str:
    """
    将内容中的概念关键词渲染为 Obsidian [[wikilink]] 双链

    策略：
    - 按概念长度从长到短匹配（避免短词先匹配干扰长词）
    - 跳过已处于 [[]] 中的内容
    - 跳过代码块内的内容
    """
    if not concepts:
        return content

    # 按长度降序排列，优先匹配长概念
    sorted_concepts = sorted(set(concepts), key=len, reverse=True)

    # 标记代码块区域，跳过
    code_regions = set()
    for m in re.finditer(r'```[\s\S]*?```', content):
        for i in range(m.start(), m.end()):
            code_regions.add(i)

    # 标记已存在双链的区域
    wikilink_regions = set()
    for m in re.finditer(r'\[\[[\s\S]*?\]\]', content):
        for i in range(m.start(), m.end()):
            wikilink_regions.add(i)

    def replace_concept(match):
        pos = match.start()
        if pos in code_regions or pos in wikilink_regions:
            return match.group(0)
        word = match.group(0)
        # 避免替换已存在的双链内容
        if pos >= 2 and content[pos-2:pos] == '[[':
            return word
        if pos + len(word) + 2 <= len(content) and content[pos+len(word):pos+len(word)+2] == ']]':
            return word
        return f'[[{word}]]'

    result = content
    for concept in sorted_concepts:
        if concept not in result:
            continue
        pattern = re.escape(concept)
        result = re.sub(pattern, replace_concept, result)

    return result
