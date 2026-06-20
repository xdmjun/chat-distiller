# -*- coding: utf-8 -*-
"""
Chat Distiller - 蒸馏输出质量验证脚本
检查输出文件的前置元数据、内容长度、标签一致性等
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def verify_file(filepath: Path) -> dict:
    """验证单个蒸馏输出文件的质量"""
    issues = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return {'file': str(filepath), 'status': 'error', 'issues': [f'读取失败: {e}']}

    if not content.strip():
        return {'file': str(filepath), 'status': 'empty', 'issues': ['文件为空']}

    # 检查 frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        issues.append('缺少 frontmatter (---)')
        return {'file': str(filepath), 'status': 'invalid', 'issues': issues}

    fm_text = fm_match.group(1)
    rel_path = filepath.relative_to(filepath.parent)

    # 解析 frontmatter 字段
    fields = {}
    for line in fm_text.strip().split('\n'):
        m = re.match(r'^(\w+):\s*(.+)$', line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")

    # 检查必填字段
    required = ['title', 'project', 'source', 'tags', 'score', 'category']
    for field in required:
        if field not in fields:
            issues.append(f'缺少必填字段: {field}')

    # 检查 title 是否为空
    title = fields.get('title', '').strip('"').strip("'")
    if not title or title.isspace():
        issues.append('title 为空')

    # 检查 score 是否为有效数字
    score_str = fields.get('score', '')
    if score_str:
        try:
            score = float(score_str)
            if score < 0 or score > 15:
                issues.append(f'score 值异常: {score}')
        except ValueError:
            issues.append(f'score 不是有效数字: {score_str}')

    # 检查 category 是否有效
    valid_categories = {'high', 'medium', 'low', 'skip'}
    category = fields.get('category', '')
    if category and category not in valid_categories:
        issues.append(f'category 值无效: {category}')

    # 检查 tags 格式
    tags_raw = fields.get('tags', '')
    if tags_raw:
        if not (tags_raw.startswith('[') and tags_raw.endswith(']')):
            issues.append('tags 格式不是 JSON 数组')

    # 检查 source 是否为空
    source = fields.get('source', '')
    if not source:
        issues.append('source 为空')

    # 检查内容主体
    body = content[fm_match.end():].strip()
    if not body:
        issues.append('frontmatter 后无内容主体')

    # 检查内容行数
    content_lines = [l for l in body.split('\n') if l.strip()]
    if len(content_lines) < 3:
        issues.append(f'内容行数过少: {len(content_lines)}')

    # 检查标题行是否匹配
    title_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    if not title_match:
        issues.append('内容缺少 # 标题行')

    status = 'ok' if not issues else 'warning'
    return {
        'file': str(filepath),
        'status': status,
        'issues': issues,
        'title': title,
        'score': score_str,
        'category': category,
        'content_lines': len(content_lines),
    }


def main():
    parser = argparse.ArgumentParser(description='验证蒸馏输出文件质量')
    parser.add_argument('--dir', required=True, help='蒸馏输出目录')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--strict', action='store_true', help='warning 级别也视为失败')
    args = parser.parse_args()

    output_dir = Path(args.dir)
    if not output_dir.exists():
        print(f"错误：目录不存在 {output_dir}")
        sys.exit(1)

    # 收集所有 .md 文件（排除 _distill-result.json、_manifest.json）
    md_files = sorted(f for f in output_dir.rglob('*.md')
                      if f.name not in ('_distill-result.json', '_manifest.json'))

    if not md_files:
        print(f"未找到 .md 文件")
        sys.exit(1)

    print(f"正在验证 {len(md_files)} 个文件...\n")

    results = []
    total_issues = 0
    for f in md_files:
        result = verify_file(f)
        results.append(result)
        if result['status'] != 'ok':
            total_issues += len(result['issues'])
            if args.verbose or result['status'] == 'error':
                print(f"  [{result['status']}] {f.name}")
                for issue in result['issues']:
                    print(f"    - {issue}")

    # 汇总
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    warn_count = sum(1 for r in results if r['status'] == 'warning')
    error_count = sum(1 for r in results if r['status'] in ('error', 'empty', 'invalid'))

    print(f"\n=== 验证统计 ===")
    print(f"总计: {len(results)} 文件")
    print(f"通过: {ok_count}")
    print(f"警告: {warn_count}")
    print(f"错误: {error_count}")
    print(f"问题总数: {total_issues}")

    # 输出 summary JSON
    summary = {
        'total': len(results),
        'ok': ok_count,
        'warning': warn_count,
        'error': error_count,
        'total_issues': total_issues,
        'files': results,
    }
    summary_path = output_dir / '_verify-result.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n验证结果: {summary_path}")

    # 退出码
    if args.strict and warn_count > 0:
        sys.exit(1)
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()