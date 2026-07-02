# -*- coding: utf-8 -*-
"""
多格式输入解析器：将各种格式的对话导出统一为 (role, text) 对话轮次
"""

from pathlib import Path
from typing import List, Tuple


def parse_dialogue(content: str, source_type: str = "agent") -> List[Tuple[str, str]]:
    """
    统一对话解析接口

    参数:
        content: 原始对话内容
        source_type: 输入类型 ("agent" / "chatgpt_json" / "claude_jsonl" / "generic" / "plain")

    返回:
        [(role, text), ...] 对话轮次列表
    """
    parsers = {
        "agent": _parse_agent_md,
        "chatgpt_json": _parse_chatgpt_json,
        "claude_jsonl": _parse_claude_jsonl,
        "generic": _parse_generic,
        "plain": _parse_plain_text,
    }
    parser = parsers.get(source_type, _parse_agent_md)
    return parser(content)


def _parse_agent_md(content: str) -> List[Tuple[str, str]]:
    """解析 Agent 导出的 .md 对话格式（**User**/**Assistant** 轮次）"""
    import re
    segments = re.split(r'\n\*\*(User|Assistant)\*\*\s*\n', content)
    blocks = []
    for i in range(1, len(segments), 2):
        if i + 1 < len(segments):
            role = segments[i].strip()
            text = segments[i + 1].strip()
            blocks.append((role, text))
    return blocks


def _parse_generic(content: str) -> List[Tuple[str, str]]:
    """解析通用对话日志（带时间戳或 User:/Assistant: 标记）"""
    import re
    blocks = []
    # 尝试匹配 "User: xxx \n Assistant: xxx" 格式
    pattern = r'(?i)(?:^|\n)(User|Assistant|Human|AI)\s*[:：]\s*(.*?)(?=\n\s*(?:User|Assistant|Human|AI)\s*[:：]|\Z)'
    for m in re.finditer(pattern, content, re.DOTALL):
        role = m.group(1).capitalize()
        if role == 'Human':
            role = 'User'
        elif role == 'AI':
            role = 'Assistant'
        text = m.group(2).strip()
        if text:
            blocks.append((role, text))
    return blocks


def _parse_chatgpt_json(content: str) -> List[Tuple[str, str]]:
    """
    解析 ChatGPT export JSON (conversations.json) 格式

    ChatGPT export 结构：
    [
      {
        "title": "...",
        "mapping": {
          "node_id": {
            "message": {
              "author": {"role": "user" / "assistant"},
              "content": {"parts": ["..."]}
            }
          }
        }
      }
    ]
    """
    import json
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    blocks = []
    if isinstance(data, list):
        for conversation in data:
            mapping = conversation.get('mapping', {}) if isinstance(conversation, dict) else {}
            # 按 create_time 排序节点
            nodes = []
            for node_id, node in mapping.items():
                msg = node.get('message') if isinstance(node, dict) else None
                if msg and isinstance(msg, dict):
                    author = msg.get('author', {})
                    role = author.get('role', '') if isinstance(author, dict) else ''
                    parts = msg.get('content', {}).get('parts', []) if isinstance(msg.get('content'), dict) else []
                    text = ' '.join(str(p) for p in parts if isinstance(p, str))
                    create_time = msg.get('create_time', 0)
                    if role in ('user', 'assistant') and text.strip():
                        nodes.append((create_time, role, text.strip()))
            nodes.sort(key=lambda x: x[0])
            for _, role, text in nodes:
                mapped_role = 'User' if role == 'user' else 'Assistant'
                blocks.append((mapped_role, text))
    return blocks


def _parse_claude_jsonl(content: str) -> List[Tuple[str, str]]:
    """
    解析 Claude.ai JSONL 导出格式

    JSONL 每行格式示例：
    {"type": "chat", "role": "user", "content": "..."}
    {"type": "chat", "role": "assistant", "content": "..."}
    """
    import json
    blocks = []
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            role = entry.get('role', '')
            text = entry.get('content', '') or entry.get('text', '')
            if role == 'user':
                blocks.append(('User', text.strip()))
            elif role in ('assistant', 'claude', 'model'):
                blocks.append(('Assistant', text.strip()))
            elif role == 'human':
                blocks.append(('User', text.strip()))
    return blocks


def _parse_plain_text(content: str) -> List[Tuple[str, str]]:
    """解析纯文本 / 未标记对话：启发式识别轮次"""
    # 简单策略：按双换行分段，奇数段算 User，偶数段算 Assistant
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    blocks = []
    for i, para in enumerate(paragraphs):
        role = "User" if i % 2 == 0 else "Assistant"
        if len(para) > 10:  # 跳过过短段
            blocks.append((role, para))
    return blocks


def detect_source_type(filepath: Path) -> str:
    """自动检测输入文件类型"""
    import json
    suffix = filepath.suffix.lower()
    if suffix == '.json':
        # 尝试解析为 ChatGPT export
        try:
            data = json.loads(filepath.read_text(encoding='utf-8', errors='ignore'))
            if isinstance(data, list) and len(data) > 0:
                if 'conversations' in data[0] or 'mapping' in data[0]:
                    return "chatgpt_json"
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return "generic"
    elif suffix == '.jsonl':
        return "claude_jsonl"
    elif suffix == '.md' or suffix == '.markdown':
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        if '**User**' in content or '**Assistant**' in content:
            return "agent"
        if re.search(r'(?mi)^(User|Assistant|Human|AI)\s*[:：]', content):
            return "generic"
        return "plain"
    else:
        return "plain"


import re  # noqa: E402
