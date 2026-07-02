# -*- coding: utf-8 -*-
"""
Chat Distiller - CLI 主入口
对话蒸馏工具：将各种格式的 AI 对话导出清洗为干净、评分过的 Markdown

使用方式:
    python scripts/distill.py --source ./raw --output ./vault
    python scripts/distill.py --source ./raw --output ./vault --ob-wiki
    python scripts/distill.py --source ./raw --dry-run
"""

import sys
import os
import json
import datetime
from pathlib import Path

import click


# ── 模块导入 ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from distiller.config import ConfigManager
from distiller.adapter import detect_source_type, parse_dialogue
from distiller.cleaner import clean_content, should_exclude
from distiller.scorer import score_6dim
from distiller.concepts import extract_concepts
from distiller.output import write_distilled_note, write_raw_archive
from distiller.renderer import render_wikilinks
from distiller.moc import write_concept_cards, write_moc, write_links_json, write_claude_md
from distiller.utils import (
    file_md5, load_manifest, save_manifest, manifest_sync,
    write_stats, generate_session_id,
)


# ── CLI 定义 ───────────────────────────────────────────────

@click.command()
@click.option('--source', '-s', required=True, help='输入路径（文件或目录）')
@click.option('--output', '-o', default='./vault', help='输出目录（默认 ./vault）')
@click.option('--config', '-c', default='config.yaml', help='配置文件路径（默认 config.yaml）')
@click.option('--ob-wiki', is_flag=True, help='启用 Obsidian 格式增强（双链+概念卡片+MOC）')
@click.option('--wiki-path', default='./wiki', help='wiki 目录路径（用于 CLAUDE.md 引用）')
@click.option('--dry-run', is_flag=True, help='仅评分不输出文件')
@click.option('--force', is_flag=True, help='强制重新处理所有文件')
@click.option('--min-score', default=2.0, type=float, help='最低评分阈值（默认 2.0，低于此值丢弃）')
@click.option('--patterns-extra', default=None, help='额外套话正则文件路径')
def main(source, output, config, ob_wiki, wiki_path, dry_run, force, min_score, patterns_extra):
    """Chat Distiller - 对话蒸馏工具"""

    # ── 1. 加载配置 ──
    click.echo(f"📋 加载配置: {config}")
    cfg_mgr = ConfigManager(config, patterns_extra)
    cfg = cfg_mgr.get()

    source_path = Path(source)
    output_dir = Path(output)
    manifest_path = output_dir / 'manifest.json'

    if not source_path.exists():
        click.echo(f"❌ 错误：源路径不存在 {source_path}")
        sys.exit(1)

    # ── 2. 收集输入文件 ──
    if source_path.is_file():
        all_files = [source_path]
        base_dir = source_path.parent
    else:
        # 支持 .md / .json / .jsonl / .txt
        all_files = []
        for ext in ('*.md', '*.markdown', '*.json', '*.jsonl', '*.txt'):
            all_files.extend(source_path.rglob(ext))
        all_files.sort()
        base_dir = source_path

    if not all_files:
        click.echo("⚠️  未找到支持的对话文件")
        sys.exit(0)

    # ── 3. 加载 manifest（增量追踪） ──
    if not force:
        manifest = load_manifest(manifest_path)
    else:
        manifest = {}

    # ── 4. 创建输出目录 ──
    if not dry_run:
        (output_dir / 'distilled' / 'notes').mkdir(parents=True, exist_ok=True)
        (output_dir / 'raw').mkdir(parents=True, exist_ok=True)

    # ── 5. 初始化统计 ──
    stats = {
        'total_input': len(all_files),
        'processed': 0,
        'skipped_manifest': 0,
        'skipped_exclude': 0,
        'too_short': 0,
        'low_score_discard': 0,
        'error': 0,
        'by_category': {},
        'by_source_type': {},
    }
    results = []
    concept_notes = {}  # {concept: [note_title, ...]} 用于 --ob-wiki
    links_index = {}    # {concept: [note_title, ...]}

    click.echo(f"\n🔍 开始处理 {len(all_files)} 个文件...\n")

    # ── 6. 主处理循环 ──
    for i, src_path in enumerate(all_files):
        if (i + 1) % 50 == 0:
            click.echo(f"  进度: {i+1}/{len(all_files)}", err=True)

        rel_path = str(src_path.relative_to(base_dir))

        # 6a. 排除检查
        if should_exclude(src_path.name, cfg):
            stats['skipped_exclude'] += 1
            continue

        # 6b. 增量检查
        current_md5 = file_md5(src_path)
        if not force and rel_path in manifest:
            if manifest[rel_path].get('md5') == current_md5:
                stats['skipped_manifest'] += 1
                entry = manifest[rel_path]
                results.append({
                    'path': entry.get('output_path', rel_path),
                    'title': entry.get('title', ''),
                    'source_type': entry.get('source_type', ''),
                    'score': entry.get('score', 0),
                    'category': entry.get('category', ''),
                    'size': entry.get('size', 0),
                })
                # 重建索引
                for c in entry.get('concepts', []):
                    concept_notes.setdefault(c, []).append(entry.get('title', ''))
                    links_index.setdefault(c, []).append(entry.get('title', ''))
                continue

        # 6c. 检测源类型
        source_type = detect_source_type(src_path)
        stats['by_source_type'][source_type] = stats['by_source_type'].get(source_type, 0) + 1

        # 6d. 读取文件
        try:
            raw_content = src_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            click.echo(f"  ⚠️  读取失败: {rel_path} — {e}")
            stats['error'] += 1
            continue

        if not raw_content.strip():
            stats['too_short'] += 1
            continue

        # 6e. 清洗
        try:
            cleaned = clean_content(raw_content, cfg)
        except Exception as e:
            click.echo(f"  ⚠️  清洗失败: {rel_path} — {e}")
            stats['error'] += 1
            continue

        if not cleaned or len(cleaned.strip()) < cfg.get('output', {}).get('min_content_chars', 50):
            stats['too_short'] += 1
            continue

        # 6f. 评分
        score_info = score_6dim(src_path, cleaned, cfg)

        if score_info['score'] < min_score:
            stats['low_score_discard'] += 1
            continue

        # 6g. 提取标题（从原始内容提取）
        title_match = __import__('re').search(r'^#\s+(.+)$', raw_content, __import__('re').MULTILINE)
        title = title_match.group(1).strip() if title_match else src_path.stem

        # 6h. 提取概念
        concepts = extract_concepts(cleaned, title, cfg)

        # 6i. 渲染双链（--ob-wiki 模式）
        display_content = cleaned
        if ob_wiki:
            display_content = render_wikilinks(cleaned, concepts)

        # 6j. 生成 session_id
        session_id = generate_session_id(source_type)

        # 6k. 构建结果
        result = {
            'title': title,
            'source': rel_path.replace('\\', '/'),
            'source_type': source_type,
            'session_id': session_id,
            'tags': [],
            'concepts': concepts,
            'score': score_info['score'],
            'category': score_info['category'],
            'reason': score_info['reason'],
            'size': len(display_content),
            'output_path': rel_path.replace('\\', '/'),
        }

        # ── 7. 输出 ──
        if not dry_run:
            # 归档原始文件
            write_raw_archive(output_dir, rel_path, raw_content)

            # 写入蒸馏笔记
            out_path = write_distilled_note(
                output_dir=output_dir,
                title=title,
                source=result['source'],
                session_id=session_id,
                tags=result['tags'],
                score=score_info['score'],
                category=score_info['category'],
                concepts=concepts,
                cleaned_content=display_content,
            )
            result['output_path'] = str(out_path.relative_to(output_dir))

            # 更新 manifest
            manifest_sync(manifest, rel_path, current_md5, result, manifest_path, stats)

        # 6m. 收集结果
        results.append({
            'path': result['output_path'],
            'title': title,
            'source_type': source_type,
            'score': score_info['score'],
            'category': score_info['category'],
            'size': result['size'],
            'concepts': concepts,
        })
        stats['processed'] += 1

        # 6n. 建立概念索引
        for c in concepts:
            concept_notes.setdefault(c, []).append(title)
            links_index.setdefault(c, []).append(title)

    # ── 8. 后处理（仅非 dry-run） ──
    if not dry_run and ob_wiki and results:
        click.echo("\n📝 生成 Obsidian 格式增强...")
        write_concept_cards(output_dir, concept_notes)
        write_moc(output_dir, results)
        write_links_json(output_dir, links_index)
        write_claude_md(output_dir, wiki_path)

    # ── 9. 保存 manifest 和统计（仅非 dry-run） ──
    stats['by_category'] = {k: stats['by_category'].get(k, 0) for k in ['high', 'medium', 'low', 'skip']}
    if not dry_run:
        save_manifest(manifest_path, manifest)
        write_stats(output_dir, stats)

    # ── 10. 输出结果 JSON ──
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    output_data = {
        'stats': stats,
        'files': results,
    }
    if not dry_run:
        result_json_path = output_dir / '_distill-result.json'
        result_json_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    # ── 11. 打印统计报告 ──
    click.echo(f"\n{'='*50}")
    click.echo(f"📊 蒸馏统计")
    click.echo(f"{'='*50}")
    click.echo(f"总计输入:     {stats['total_input']}")
    click.echo(f"处理成功:     {stats['processed']}")
    click.echo(f"  高分:       {stats['by_category'].get('high', 0)}")
    click.echo(f"  中分:       {stats['by_category'].get('medium', 0)}")
    click.echo(f"  低分:       {stats['by_category'].get('low', 0)}")
    click.echo(f"  跳过:       {stats['by_category'].get('skip', 0)}")
    click.echo(f"跳过(清单):   {stats['skipped_manifest']}")
    click.echo(f"跳过(排除):   {stats['skipped_exclude']}")
    click.echo(f"内容过短:     {stats['too_short']}")
    click.echo(f"评分丢弃:     {stats['low_score_discard']}")
    click.echo(f"错误:         {stats['error']}")
    click.echo(f"\n来源类型:     {stats['by_source_type']}")

    if not dry_run:
        click.echo(f"\n📁 输出目录: {output_dir.resolve()}")
        click.echo(f"📄 结果 JSON: {result_json_path.resolve()}")

    # 退出码
    if stats['error'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
