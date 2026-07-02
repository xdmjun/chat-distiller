# -*- coding: utf-8 -*-
"""
工具函数：文件操作、哈希、清单管理
"""

import hashlib
import json
from pathlib import Path


def file_md5(filepath: Path) -> str:
    """计算文件 MD5 哈希"""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


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


def generate_session_id(source_type: str, prefix: str = "") -> str:
    """生成唯一会话 ID"""
    import datetime
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    suffix = prefix if prefix else ts
    return f"{source_type}_{suffix}"


def safe_filename(text: str, max_len: int = 80) -> str:
    """将标题转为安全文件名"""
    safe = re.sub(r'[\\/:*?"<>|]', '_', text)
    safe = safe.strip().replace(' ', '_')[:max_len]
    return safe


def manifest_sync(
    manifest: dict,
    rel_path: str,
    current_md5: str,
    result: dict,
    manifest_path: Path,
    stats: dict,
) -> dict:
    """
    增量追踪同步：记录已处理文件信息到 manifest，更新统计

    参数:
        manifest: 当前 manifest 字典
        rel_path: 文件的相对路径
        current_md5: 文件的 MD5 哈希
        result: 蒸馏结果
        manifest_path: manifest.json 路径
        stats: 统计数据字典（会被原地修改）

    返回:
        更新后的 manifest
    """
    manifest[rel_path] = {
        'md5': current_md5,
        'output_path': result.get('output_path', rel_path.replace('\\', '/')),
        'title': result.get('title', ''),
        'source_type': result.get('source_type', ''),
        'session_id': result.get('session_id', ''),
        'tags': result.get('tags', []),
        'concepts': result.get('concepts', []),
        'score': result.get('score', 0),
        'category': result.get('category', ''),
        'size': result.get('size', 0),
        'reason': result.get('reason', ''),
    }

    # 更新统计
    category = result.get('category', 'skip')
    stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

    # 持久化
    save_manifest(manifest_path, manifest)

    return manifest


def write_stats(output_dir: Path, stats: dict):
    """写入 _stats.json 统计文件"""
    import json
    now = __import__('datetime').datetime.now().isoformat()
    stats['updated'] = now
    stats_path = Path(output_dir) / '_stats.json'
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


import re  # noqa: E402 (用于 safe_filename)
