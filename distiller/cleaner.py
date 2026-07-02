# -*- coding: utf-8 -*-
"""
规则清洗引擎：移除 AI 套话、操作性过渡语句，保留核心知识内容
"""

import re
from typing import List


def clean_content(content: str, config: dict) -> str:
    """
    清洗对话内容主入口
    1. 解析对话轮次
    2. 仅保留 Assistant 块
    3. 对每个 Assistant 块做规则清洗
    4. 合并结果
    """
    from .adapter import parse_dialogue
    blocks = parse_dialogue(content)

    if not blocks:
        return content.strip()

    assistant_texts = []
    for role, text in blocks:
        if role == 'Assistant':
            cleaned = clean_assistant_block(text, config)
            if cleaned and len(cleaned) > 20:
                assistant_texts.append(cleaned)

    result = '\n\n'.join(assistant_texts)
    result = re.sub(r'(##\s+.+)\n\n\1', r'\1', result)

    return result.strip()


def clean_assistant_block(text: str, config: dict) -> str:
    """清洗单个 Assistant 块的内容"""
    # 合并中文操作性语句 + 英文套话
    operational_patterns = config.get('operational_patterns', [])
    english_platitudes = config.get('english_platitudes', [])

    lines = text.split('\n')
    cleaned = []
    in_code_block = False
    prev_empty = False

    for line in lines:
        stripped = line.strip()

        # 跟踪代码块
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            cleaned.append(line)
            prev_empty = False
            continue

        if in_code_block:
            cleaned.append(line)
            prev_empty = False
            continue

        # 跳过空行去重
        if not stripped:
            if prev_empty:
                continue
            prev_empty = True
            cleaned.append('')
            continue
        prev_empty = False

        # 跳过文件引用 (file:///)
        if 'file:///' in stripped:
            continue

        # 跳过 "Relevant Code Snippets" 标题
        if re.match(r'^###\s*Relevant Code Snippets', stripped):
            continue

        # 跳过数字编号的文件引用行
        if re.match(r'^\d+\.\s+\S+\.?\w*:L\d+-L\d+', stripped):
            continue

        # 跳过 "—" 开头的文件描述行
        if stripped.startswith('— ') and len(stripped) < 200:
            if any(kw in stripped for kw in ['该文件', '继续显示', '展示了', '表示了',
                                              '对话', '聊天', '模型', '文件的', '代码',
                                              '包含', '配置', '显示了', '消息']):
                continue

        # 跳过中英文操作性过渡语句
        is_op = False
        for pattern in operational_patterns:
            if re.search(pattern, stripped):
                is_op = True
                break
        if not is_op:
            for pattern in english_platitudes:
                if re.search(pattern, stripped):
                    is_op = True
                    break
        if is_op:
            continue

        # 跳过 SEARCH QUERY / tool 输出行
        if (stripped.startswith('SEARCH QUERY:') or
            stripped.startswith('Project Directory Paths:') or
            stripped.startswith('Use appropriate tools') or
            stripped.startswith('Respond in ')):
            continue

        cleaned.append(line)

    result = '\n'.join(cleaned)

    # 后处理
    result = re.sub(r'\[([^\]]+)\]\(file:///[^\)]+\)', r'\1', result)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    return result.strip()


def should_exclude(filename: str, config: dict) -> bool:
    """检查文件是否应该排除"""
    stem = Path(filename).stem
    for pattern in config.get('exclude_patterns', []):
        if re.search(pattern, stem, re.IGNORECASE):
            return True
    return False


from pathlib import Path  # noqa: E402
