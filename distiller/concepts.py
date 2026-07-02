# -*- coding: utf-8 -*-
"""
规则概念抽取：基于 jieba 分词 + 词频统计 + 同义归一，生成 concepts 列表
"""

import re
from typing import List


def extract_concepts(content: str, title: str, config: dict) -> List[str]:
    """
    从清洗后的内容中抽取关键概念

    策略:
    1. 标签关键词映射中已有的直接匹配
    2. jieba 分词 + 词频统计提取高频名词短语
    3. 同义归一化
    """
    concepts = set()

    # 1. 从标签关键词映射提取（高置信度）
    tag_keywords = config.get('tag_keywords', {})
    combined = title + ' ' + content[:5000]
    for keyword, tag in tag_keywords.items():
        if keyword in combined:
            concepts.add(tag)

    # 2. jieba 分词提取高频实词
    try:
        import jieba
        import jieba.posseg as pseg
        # 添加用户自定义词典
        for kw in tag_keywords.keys():
            jieba.add_word(kw)

        words = pseg.lcut(content[:8000])
        freq = {}
        for w, pos in words:
            # 只保留名词、专有名词、动词、英文术语
            if pos.startswith(('n', 'v', 'eng')) and len(w) >= 2 and len(w) <= 20:
                freq[w] = freq.get(w, 0) + 1

        # 词频归一化 + 取 Top N
        top_concepts = sorted(freq.items(), key=lambda x: -x[1])[:10]
        for word, count in top_concepts:
            if count >= 2:  # 至少出现 2 次
                concepts.add(word)
    except ImportError:
        pass  # jieba 未安装时不报错

    # 3. 从标题中提取关键概念（# 号后的第一个名词短语）
    title_concepts = re.findall(r'[A-Z\u4e00-\u9fff]{2,}', title)
    for tc in title_concepts[:3]:
        if len(tc) >= 2:
            concepts.add(tc)

    return sorted(list(concepts))[:10]  # 最多 10 个概念


def normalize_synonym(concept: str, synonym_map: dict = None) -> str:
    """同义归一：将概念映射到标准名称"""
    if synonym_map:
        return synonym_map.get(concept, concept)
    return concept
