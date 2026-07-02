# -*- coding: utf-8 -*-
"""
Chat Distiller - 蒸馏输出质量验证脚本（MVP v2.0）
检查输出文件的 frontmatter、评分、概念、内容完整性等
"""

import argparse
import json
import re
import sys
from pathlib import Path


def verify_file(filepath: Path, strict: bool = False) -> dict:
    """验证单个蒸馏输出文件的质量"""
    issues = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return {'file': str(filepath), 'status': 'error', 'issues': [f'读取失败: {e}']}

    if not content.strip():
        return {'file': str(filepath), 'status': 'empty', 'issues': ['文件为空']}

    # 检查 frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n(?:---|\.\.\.)', content, re.DOTALL)
    if not fm_match:
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        issues.append('缺少 frontmatter (---)')
        return {'file': str(filepath), 'status': 'invalid', 'issues': issues}

    fm_text = fm_match.group(1).strip()

    # 解析 frontmatter 字段（YAML 简易解析）
    fields = {}
    current_key = None
    current_value = []
    for line in fm_text.split('\n'):
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if m:
            if current_key:
                fields[current_key] = '\n'.join(current_value).strip()
            current_key = m.group(1)
            current_value = [m.group(2).strip()]
        elif current_key and line.startswith(' '):
            current_value.append(line.strip())
        elif current_key:
            current_value.append(line)
    if current_key:
        fields[current_key] = '\n'.join(current_value).strip()

    # 清理引号
    for k, v in fields.items():
        if isinstance(v, str):
            fields[k] = v.strip('"').strip("'")

    # 检查必填字段（PRD §2.4 格式）
    required = ['title', 'source', 'session_id', 'tags', 'score', 'category', 'concepts', 'created']
    for field in required:
        if field not in fields:
            issues.append(f'缺少必填字段: {field}')

    # 检查 title
    title = fields.get('title', '')
    if not title or title.isspace():
        issues.append('title 为空')

    # 检查 source
    source = fields.get('source', '')
    if not source:
        issues.append('source 为空')

    # 检查 session_id
    session_id = fields.get('session_id', '')
    if not session_id:
        issues.append('session_id 为空')

    # 检查 score
    score_str = fields.get('score', '')
    if score_str:
        try:
            score = float(score_str)
            if score < 0 or score > 15:
                issues.append(f'score 值超出范围 (0-15): {score}')
        except ValueError:
            issues.append(f'score 不是有效数字: {score_str}')

    # 检查 category
    valid_categories = {'high', 'medium', 'low', 'skip'}
    category = fields.get('category', '')
    if category and category not in valid_categories:
        issues.append(f'category 值无效: {category}')

    # 验证 score 与 category 一致性
    if score_str and category:
        try:
            s = float(score_str)
            if s >= 6 and category != 'high':
                issues.append(f'score={s} 但 category="{category}"，应为 "high"')
            elif 3.5 <= s < 6 and category != 'medium':
                issues.append(f'score={s} 但 category="{category}"，应为 "medium"')
            elif 2.0 <= s < 3.5 and category != 'low':
                issues.append(f'score={s} 但 category="{category}"，应为 "low"')
            elif s < 2.0:
                if category != 'skip':
                    issues.append(f'score={s} 但 category="{category}"，应为 "skip"')
        except ValueError:
            pass

    # 检查 tags 格式
    tags_raw = fields.get('tags', '')
    if tags_raw:
        if not (tags_raw.startswith('[') and tags_raw.endswith(']')):
            issues.append('tags 格式不是 JSON 数组')
        else:
            try:
                tags = json.loads(tags_raw)
                if not isinstance(tags, list):
                    issues.append('tags 不是数组')
            except json.JSONDecodeError:
                issues.append('tags JSON 解析失败')

    # 检查 concepts 格式
    concepts_raw = fields.get('concepts', '')
    if concepts_raw:
        if not (concepts_raw.startswith('[') and concepts_raw.endswith(']')):
            issues.append('concepts 格式不是 JSON 数组')
        else:
            try:
                concepts = json.loads(concepts_raw)
                if not isinstance(concepts, list):
                    issues.append('concepts 不是数组')
            except json.JSONDecodeError:
                issues.append('concepts JSON 解析失败')

    # 检查 created 时间格式
    created = fields.get('created', '')
    if created:
        if not re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', created):
            issues.append(f'created 时间格式不规范: {created}')

    # 检查内容主体
    body = content[fm_match.end():].strip()
    if not body:
        issues.append('frontmatter 后无内容主体')
    else:
        # 检查标题行
        if not re.search(r'^#\s+.+$', body, re.MULTILINE):
            issues.append('内容缺少 # 标题行')

        # 检查内容行数
        content_lines = [l for l in body.split('\n') if l.strip()]
        if len(content_lines) < 3:
            issues.append(f'内容行数过少: {len(content_lines)}')

    status = 'ok' if not issues else 'warning'
    return {
        'file': str(filepath),
        'status': status,
        'issues': issues,
        'title': title,
        'score': score_str,
        'category': category,
        'content_lines': len([l for l in body.split('\n') if l.strip()]) if body else 0,
    }


def verify_vault_structure(vault_dir: Path) -> dict:
    """验证 vault 目录结构完整性"""
    structure_issues = []

    expected_dirs = [
        vault_dir / 'distilled' / 'notes',
        vault_dir / 'raw',
    ]
    for d in expected_dirs:
        if not d.exists():
            structure_issues.append(f'缺失目录: {d.relative_to(vault_dir)}')

    expected_files = [
        vault_dir / 'manifest.json',
        vault_dir / '_stats.json',
    ]
    for f in expected_files:
        if not f.exists():
            structure_issues.append(f'缺失文件: {f.relative_to(vault_dir)}')

    return structure_issues


def main():
    parser = argparse.ArgumentParser(description='验证蒸馏输出文件质量（v2.0）')
    parser.add_argument('--dir', required=True, help='蒸馏输出目录（vault/）')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--strict', action='store_true', help='warning 级别也视为失败')
    parser.add_argument('--check-ob-wiki', action='store_true', help='同时验证 --ob-wiki 产物')
    args = parser.parse_args()

    output_dir = Path(args.dir)
    if not output_dir.exists():
        print(f"❌ 错误：目录不存在 {output_dir}")
        sys.exit(1)

    # 验证 vault 结构
    print(f"📁 验证 vault 结构: {output_dir}\n")
    structure_issues = verify_vault_structure(output_dir)
    if structure_issues:
        print("  结构问题:")
        for iss in structure_issues:
            print(f"    ⚠️   {iss}")
    else:
        print("  ✅ vault 结构完整")

    # 收集蒸馏笔记
    notes_dir = output_dir / 'distilled' / 'notes'
    if notes_dir.exists():
        md_files = sorted(notes_dir.glob('*.md'))
    else:
        md_files = sorted(f for f in output_dir.rglob('*.md')
                          if f.name not in ('_distill-result.json', '_manifest.json')
                          and 'concepts' not in str(f) and 'moc' not in str(f))

    if not md_files:
        print("\n⚠️  未找到蒸馏笔记文件")
        sys.exit(0)

    print(f"\n📝 正在验证 {len(md_files)} 个笔记文件...\n")

    results = []
    total_issues = 0
    for f in md_files:
        result = verify_file(f, args.strict)
        results.append(result)
        if result['status'] != 'ok':
            total_issues += len(result['issues'])
            if args.verbose or result['status'] == 'error':
                print(f"  [{result['status']}] {f.name}")
                for issue in result['issues']:
                    print(f"    - {issue}")
            elif not args.verbose:
                pass  # 不显示 warnings

    # 验证 --ob-wiki 产物（如果存在）
    ob_wiki_artifacts = {}
    if args.check_ob_wiki or (output_dir / 'distilled' / 'concepts').exists():
        print("\n🔗 检查 --ob-wiki 产物...")
        concepts_dir = output_dir / 'distilled' / 'concepts'
        moc_dir = output_dir / 'distilled' / 'moc'
        claude_dir = output_dir / '.claude'
        index_dir = output_dir / '_index'

        ob_wiki_artifacts = {
            'concepts': list(concepts_dir.glob('*.md')) if concepts_dir.exists() else [],
            'moc': list(moc_dir.glob('*.md')) if moc_dir.exists() else [],
            'claude_md': list(claude_dir.glob('*.md')) if claude_dir.exists() else [],
            'links_json': list(index_dir.glob('*.json')) if index_dir.exists() else [],
        }

        for artifact_type, files in ob_wiki_artifacts.items():
            if files:
                print(f"  ✅ {artifact_type}: {len(files)} 个文件")
            else:
                print(f"  ⚠️  {artifact_type}: 缺失")

    # 汇总
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    warn_count = sum(1 for r in results if r['status'] == 'warning')
    error_count = sum(1 for r in results if r['status'] in ('error', 'empty', 'invalid'))

    # 评分分布
    score_dist = {'high': 0, 'medium': 0, 'low': 0, 'skip': 0, 'unknown': 0}
    for r in results:
        cat = r.get('category', '')
        if cat in score_dist:
            score_dist[cat] += 1
        else:
            score_dist['unknown'] += 1

    print(f"\n{'='*50}")
    print(f"📊 验证统计")
    print(f"{'='*50}")
    print(f"总计:       {len(results)} 文件")
    print(f"通过:       {ok_count}")
    print(f"警告:       {warn_count}")
    print(f"错误:       {error_count}")
    print(f"问题总数:   {total_issues}")
    print(f"\n评分分布:")
    for cat, count in score_dist.items():
        if count > 0:
            print(f"  {cat}: {count}")

    if ob_wiki_artifacts:
        print(f"\n--ob-wiki 产物:")
        for artifact_type, files in ob_wiki_artifacts.items():
            print(f"  {artifact_type}: {len(files)} 文件")

    # 输出 summary JSON
    summary = {
        'total': len(results),
        'ok': ok_count,
        'warning': warn_count,
        'error': error_count,
        'total_issues': total_issues,
        'score_distribution': score_dist,
        'vault_structure_issues': structure_issues,
        'files': results,
    }
    summary_path = output_dir / '_verify-result.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ 验证结果: {summary_path}")

    # 退出码
    if args.strict and warn_count > 0:
        sys.exit(1)
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
