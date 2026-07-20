# -*- coding: utf-8 -*-
"""
7 维评分引擎：信息密度、技术深度、结构化数据、白名单匹配、关键词、长度惩罚、套话惩罚
输出 0-18 分 + category 分类
"""

import re


def score_6dim(filepath, cleaned_content: str, config: dict) -> dict:
    """
    7 维度评分，总分 0-18

    维度:
    1. 信息密度 (0-2): 文件大小 / 内容量
    2. 技术深度 (0-3): 代码块 + 标题结构
    3. 结构化数据 (0-3): 表格、IP地址、架构图、键值对等结构化内容
    4. 白名单匹配 (0-5): 领域规则命中
    5. 标题关键词 (0-3): 高价值关键词命中标题
    6. 内容关键词 (0-2): 高价值关键词命中内容
    7. 惩罚项 (-2~0): 低价值关键词 / 套话残留惩罚
    """
    name = filepath.stem if hasattr(filepath, 'stem') else str(filepath)
    score = 0.0
    reasons = []

    # D1: 信息密度 (0-2)
    file_size = len(cleaned_content.encode('utf-8'))
    if file_size > 20480:
        score += 2
        reasons.append(f'info_dense(>{file_size//1024}KB)')
    elif file_size > 10240:
        score += 1.5
        reasons.append(f'info_medium(>{file_size//1024}KB)')
    elif file_size > 5120:
        score += 1
        reasons.append(f'info_light(>{file_size//1024}KB)')

    # D2: 技术深度 (0-3)
    code_blocks = cleaned_content.count('```') // 2
    if code_blocks >= 5:
        score += 2
        reasons.append(f'deep_code({code_blocks})')
    elif code_blocks >= 2:
        score += 1
        reasons.append(f'has_code({code_blocks})')

    headings = len(re.findall(r'(?m)^#{1,3}\s', cleaned_content))
    if headings >= 5:
        score += 1
        reasons.append(f'structured({headings} headings)')
    elif headings >= 2:
        score += 0.5
        reasons.append(f'some_headings({headings})')

    # D3: 结构化数据 (0-3) — 新增维度，识别表格、IP、架构图、键值对
    struct_score = 0

    # 3a: Markdown 表格行
    table_rows = len(re.findall(r'^\|.+\|$', cleaned_content, re.MULTILINE))
    if table_rows >= 8:
        struct_score += 1.5
        reasons.append(f'tables({table_rows})')
    elif table_rows >= 3:
        struct_score += 1
        reasons.append(f'some_tables({table_rows})')

    # 3b: IP 地址 + 端口组合
    ip_ports = len(re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', cleaned_content))
    if ip_ports >= 5:
        struct_score += 1
        reasons.append(f'ip_data({ip_ports})')
    elif ip_ports >= 2:
        struct_score += 0.5
        reasons.append(f'some_ip({ip_ports})')

    # 3c: ASCII 架构图/流程图
    ascii_diagrams = len(re.findall(r'[┌└├│┐┘┤─→↓←↑↔↕]', cleaned_content))
    if ascii_diagrams >= 5:
        struct_score += 0.5
        reasons.append(f'diagram({ascii_diagrams})')

    struct_bonus = min(struct_score, 3)
    score += struct_bonus

    # D3: 白名单匹配 (0-5)
    whitelist_score = 0
    whitelist_reasons = []
    for rule in config.get('whitelist_rules', []):
        patterns = rule.get('patterns', [])
        match_type = rule.get('match_type', 'any')
        min_matches = rule.get('min_matches', 1)
        rule_score = rule.get('score', 1)

        if match_type == 'any':
            matches = sum(1 for p in patterns if re.search(p, cleaned_content, re.IGNORECASE))
            if matches >= min_matches:
                whitelist_score += rule_score
                whitelist_reasons.append(f"{rule['name']}({matches})")
        else:  # all
            if all(re.search(p, cleaned_content, re.IGNORECASE) for p in patterns):
                whitelist_score += rule_score
                whitelist_reasons.append(rule['name'])

    whitelist_bonus = min(whitelist_score, 5)
    if whitelist_bonus > 0:
        score += whitelist_bonus
        reasons.append(f'whitelist({", ".join(whitelist_reasons)})')

    # D4: 标题关键词 (0-3)
    title_score = sum(1 for kw in config.get('high_value_keywords', []) if kw in name)
    title_bonus = min(title_score, 3)
    score += title_bonus
    if title_bonus > 0:
        reasons.append(f'title_kw({title_bonus})')

    # D5: 内容关键词 (0-2)
    content_score = sum(0.2 for kw in config.get('high_value_keywords', []) if kw in cleaned_content)
    content_bonus = min(int(content_score), 2)
    score += content_bonus
    if content_bonus > 0:
        reasons.append(f'content_kw({content_bonus})')

    # D6: 惩罚项 (-2~0)
    penalty = 0
    low_count = sum(1 for kw in config.get('low_value_keywords', []) if kw in cleaned_content)
    if low_count >= 3:
        penalty -= 1
        reasons.append('low_value_penalty')
    # 套话残留量过大惩罚
    if len(cleaned_content) > 0:
        ratio = low_count * 10 / len(cleaned_content)
        if ratio > 0.05:
            penalty -= 0.5
            reasons.append('platitude_penalty')
    score += penalty

    # 确保不低于 0
    score = max(0, score)

    # 分类
    thresholds = config.get('output', {}).get('thresholds', {'high': 6, 'medium': 3.5, 'low': 2})
    if score >= thresholds.get('high', 6):
        category = 'high'
    elif score >= thresholds.get('medium', 3.5):
        category = 'medium'
    elif score >= thresholds.get('low', 2):
        category = 'low'
    else:
        category = 'skip'

    return {
        'score': round(score, 1),
        'category': category,
        'reason': '; '.join(reasons),
    }
