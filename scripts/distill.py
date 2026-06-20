# -*- coding: utf-8 -*-
"""
Chat Distiller - 对话蒸馏脚本
支持配置化白名单、增量处理、项目合并
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_manifest(manifest_path: Path) -> dict:
    """加载已处理文件清单"""
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_manifest(manifest_path: Path, manifest: dict):
    """保存已处理文件清单"""
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def file_md5(filepath: Path) -> str:
    """计算文件 MD5"""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def should_exclude(filename: str, config: dict) -> bool:
    """检查文件是否应该排除"""
    stem = Path(filename).stem
    for pattern in config.get('exclude_patterns', []):
        if re.search(pattern, stem, re.IGNORECASE):
            return True
    return False


def score_file(filepath: Path, cleaned_content: str, config: dict) -> dict:
    """对清洗后的文件内容进行评分"""
    file_size = len(cleaned_content.encode('utf-8'))
    name = filepath.stem
    score = 0.0
    reasons = []

    # 1. 文件大小评分 (0-2分)
    if file_size > 20480:
        score += 2
        reasons.append(f'large_file(>{file_size//1024}KB)')
    elif file_size > 10240:
        score += 1.5
        reasons.append(f'medium_file(>{file_size//1024}KB)')
    elif file_size > 5120:
        score += 1
        reasons.append(f'small_medium(>{file_size//1024}KB)')

    # 2. 标题关键词评分 (0-3分)
    title_score = sum(1 for kw in config.get('high_value_keywords', []) if kw in name)
    title_bonus = min(title_score, 3)
    score += title_bonus
    if title_bonus > 0:
        reasons.append(f'title_keywords({title_bonus})')

    # 3. 内容结构评分 (0-3分)
    code_blocks = cleaned_content.count('```') // 2
    if code_blocks >= 5:
        score += 2
        reasons.append(f'many_code_blocks({code_blocks})')
    elif code_blocks >= 2:
        score += 1
        reasons.append(f'some_code_blocks({code_blocks})')

    headings = len(re.findall(r'(?m)^#{1,3}\s', cleaned_content))
    if headings >= 5:
        score += 1
        reasons.append(f'structured({headings} headings)')

    # 4. 内容关键词评分 (0-2分) — 基于清洗后内容
    content_score = sum(0.2 for kw in config.get('high_value_keywords', []) if kw in cleaned_content)
    content_bonus = min(int(content_score), 2)
    score += content_bonus
    if content_bonus > 0:
        reasons.append(f'content_keywords({content_bonus})')

    # 5. 低价值惩罚 — 基于清洗后内容
    low_count = sum(1 for kw in config.get('low_value_keywords', []) if kw in cleaned_content)
    if low_count >= 3:
        score -= 1
        reasons.append('low_value_penalty')

    # 6. 白名单规则评分 — 基于清洗后内容
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

    # 应用白名单加分（最多 +5 分）
    whitelist_bonus = min(whitelist_score, 5)
    if whitelist_bonus > 0:
        score += whitelist_bonus
        reasons.append(f'whitelist({", ".join(whitelist_reasons)})')

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


def parse_dialogue(content: str) -> list:
    """将对话内容解析为段落列表：(role, text)"""
    segments = re.split(r'\n\*\*(User|Assistant)\*\*\s*\n', content)
    blocks = []
    for i in range(1, len(segments), 2):
        if i + 1 < len(segments):
            role = segments[i].strip()
            text = segments[i + 1].strip()
            blocks.append((role, text))
    return blocks


def clean_assistant_block(text: str, config: dict) -> str:
    """清洗单个 Assistant 块的内容"""
    operational_patterns = config.get('operational_patterns', [])
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

        # 跳过操作性过渡语句
        is_op = False
        for pattern in operational_patterns:
            if re.search(pattern, stripped):
                is_op = True
                break
        if is_op:
            continue

        # 跳过 SEARCH QUERY 块
        if stripped.startswith('SEARCH QUERY:'):
            continue
        if stripped.startswith('Project Directory Paths:'):
            continue
        if stripped.startswith('Use appropriate tools'):
            continue
        if stripped.startswith('Respond in '):
            continue

        cleaned.append(line)

    result = '\n'.join(cleaned)

    # 后处理
    result = re.sub(r'\[([^\]]+)\]\(file:///[^\)]+\)', r'\1', result)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    return result.strip()


def clean_content(content: str, config: dict) -> str:
    """清洗对话内容，只保留 Assistant 的知识内容"""
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


def extract_tags(content: str, title: str, config: dict) -> list:
    """从内容中提取标签"""
    tags = set()
    tag_keywords = config.get('tag_keywords', {})
    max_tags = config.get('output', {}).get('max_tags', 8)

    combined = title + ' ' + content[:3000]
    for keyword, tag in tag_keywords.items():
        if keyword in combined:
            tags.add(tag)

    return sorted(list(tags))[:max_tags]


def extract_project_name(rel_path: str, config: dict) -> str:
    """提取项目名，处理合并"""
    parts = rel_path.split(os.sep)
    project = parts[0]
    return config.get('project_merge', {}).get(project, project)


def distill_file(src_path: Path, rel_path: str, config: dict) -> dict:
    """蒸馏单个文件"""
    try:
        content = src_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

    if not content.strip():
        return {'status': 'empty'}

    # 提取标题
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else src_path.stem
    if any(kw in title for kw in ['Workspace', '**User', '**Assistant', '---', '>']):
        title = src_path.stem
    if not title or title.isspace():
        title = src_path.stem

    # 清洗内容
    cleaned = clean_content(content, config)

    min_chars = config.get('output', {}).get('min_content_chars', 50)
    if len(cleaned.strip()) < min_chars:
        return {'status': 'too_short_after_clean'}

    # 移除重复标题
    if cleaned.startswith(f'# {title}'):
        cleaned = cleaned[len(f'# {title}'):].strip()
    elif cleaned.startswith(f'# {title}\n'):
        cleaned = cleaned[len(f'# {title}\n'):].strip()

    # 过滤内容过少的文件
    min_lines = config.get('output', {}).get('min_content_lines', 5)
    content_lines = [l for l in cleaned.split('\n') if l.strip()]
    if len(content_lines) < min_lines:
        return {'status': 'too_few_content_lines'}

    # 提取项目名和标签
    project = extract_project_name(rel_path, config)
    tags = extract_tags(cleaned, title, config)

    # 评分 — 基于清洗后内容，更真实反映实际保留内容的价值
    score_info = score_file(src_path, cleaned, config)

    # 构建 frontmatter
    safe_title = title.replace('"', "'")
    safe_source = rel_path.replace(os.sep, '/')
    tags_json = json.dumps(tags, ensure_ascii=False)
    frontmatter = f'---\ntitle: "{safe_title}"\nproject: "{project}"\nsource: "{safe_source}"\ntags: {tags_json}\nscore: {score_info["score"]}\ncategory: "{score_info["category"]}"\n---'

    final = f"{frontmatter}\n\n# {title}\n\n{cleaned}"

    return {
        'status': 'ok',
        'content': final,
        'title': title,
        'project': project,
        'tags': tags,
        'size': len(final),
        'score': score_info['score'],
        'category': score_info['category'],
        'reason': score_info['reason'],
    }


def main():
    parser = argparse.ArgumentParser(description='Chat Distiller - 对话蒸馏脚本')
    parser.add_argument('--source', required=True, help='源文件目录')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--config', required=True, help='配置文件路径')
    parser.add_argument('--incremental', action='store_true', help='增量处理模式')
    parser.add_argument('--force', action='store_true', help='强制重新处理所有文件')
    parser.add_argument('--score-only', action='store_true', help='仅评分，不输出文件')
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    source_dir = Path(args.source)
    output_dir = Path(args.output)
    manifest_path = output_dir / '_manifest.json'

    if not source_dir.exists():
        print(f"错误：源目录不存在 {source_dir}")
        sys.exit(1)

    # 加载清单
    manifest = {} if args.force else load_manifest(manifest_path)

    # 创建输出目录
    if not args.score_only:
        output_dir.mkdir(parents=True, exist_ok=True)

    all_files = list(source_dir.rglob('*.md'))
    results = []
    stats = {
        'ok': 0, 'error': 0, 'empty': 0,
        'too_short_after_clean': 0, 'too_few_content_lines': 0,
        'skipped': 0
    }

    print(f"开始处理 {len(all_files)} 个文件...", flush=True)

    for i, src_path in enumerate(all_files):
        if (i + 1) % 100 == 0:
            print(f"  已处理 {i+1} / {len(all_files)} 文件...", flush=True)

        rel_path = str(src_path.relative_to(source_dir))

        # 检查是否排除
        if should_exclude(src_path.name, config):
            stats['skipped'] += 1
            continue

        # 增量处理：检查文件是否已处理
        current_md5 = file_md5(src_path)
        if args.incremental and rel_path in manifest:
            if manifest[rel_path].get('md5') == current_md5:
                stats['skipped'] += 1
                # 加载已有结果
                results.append({
                    'path': manifest[rel_path].get('output_path', rel_path),
                    'title': manifest[rel_path].get('title', ''),
                    'project': manifest[rel_path].get('project', ''),
                    'tags': manifest[rel_path].get('tags', []),
                    'size': manifest[rel_path].get('size', 0),
                    'score': manifest[rel_path].get('score', 0),
                    'category': manifest[rel_path].get('category', ''),
                    'reason': manifest[rel_path].get('reason', ''),
                })
                continue

        # 蒸馏
        result = distill_file(src_path, rel_path, config)
        status = result.get('status', 'unknown')
        stats[status] = stats.get(status, 0) + 1

        if status == 'ok':
            # 确定输出路径
            project = result['project']
            original_project = rel_path.split(os.sep)[0]
            project_merge = config.get('project_merge', {})
            if original_project in project_merge:
                rest = os.sep.join(rel_path.split(os.sep)[1:])
                out_rel = os.path.join(project, rest)
            else:
                out_rel = rel_path

            # 写入文件
            if not args.score_only:
                out_path = output_dir / out_rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(result['content'], encoding='utf-8')

            # 更新清单
            manifest[rel_path] = {
                'md5': current_md5,
                'output_path': out_rel.replace(os.sep, '/'),
                'title': result['title'],
                'project': result['project'],
                'tags': result['tags'],
                'size': result['size'],
                'score': result['score'],
                'category': result['category'],
                'reason': result['reason'],
            }

            results.append({
                'path': out_rel.replace(os.sep, '/'),
                'title': result['title'],
                'project': result['project'],
                'tags': result['tags'],
                'size': result['size'],
                'score': result['score'],
                'category': result['category'],
                'reason': result['reason'],
            })

    # 保存清单
    if not args.score_only:
        save_manifest(manifest_path, manifest)

    # 输出统计
    print(f"\n=== 蒸馏统计 ===")
    print(f"总计: {len(all_files)} 文件")
    print(f"成功: {stats['ok']}")
    print(f"跳过: {stats['skipped']}")
    print(f"过短: {stats.get('too_short_after_clean', 0)}")
    print(f"内容过少: {stats.get('too_few_content_lines', 0)}")
    print(f"错误: {stats['error']}")

    # 输出结果 JSON
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    output = {
        'stats': {
            'total_input': len(all_files),
            'distilled': stats['ok'],
            'skipped': stats['skipped'],
            'too_short': stats.get('too_short_after_clean', 0),
            'too_few_lines': stats.get('too_few_content_lines', 0),
            'errors': stats['error'],
        },
        'files': results,
    }
    result_file = output_dir / '_distill-result.json'
    result_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n结果 JSON: {result_file}")
    print(f"输出目录: {output_dir}")


if __name__ == '__main__':
    main()