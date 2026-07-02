# -*- coding: utf-8 -*-
"""
配置管理：加载、热重载、额外规则合并
"""

import os
import time
from pathlib import Path

import yaml


class ConfigManager:
    """配置管理器，支持热重载和额外规则合并"""

    def __init__(self, config_path: str, patterns_extra: str = None):
        self.config_path = config_path
        self.patterns_extra_path = patterns_extra
        self._config = None
        self._mtime = 0
        self._extra_mtime = 0
        self.load()

    def load(self) -> dict:
        """加载（或重新加载）配置"""
        config = self._load_yaml(self.config_path)

        # 合并额外套话正则文件
        if self.patterns_extra_path and os.path.exists(self.patterns_extra_path):
            extra = self._load_yaml(self.patterns_extra_path)
            self._merge_extra_patterns(config, extra)

        self._config = config
        return config

    def get(self) -> dict:
        """获取配置，检测文件变更则自动重载"""
        current_mtime = self._get_mtime(self.config_path)
        if current_mtime > self._mtime:
            self.load()
        if self.patterns_extra_path:
            extra_mtime = self._get_mtime(self.patterns_extra_path)
            if extra_mtime > self._extra_mtime:
                self.load()
        return self._config

    def _load_yaml(self, path: str) -> dict:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _get_mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def _merge_extra_patterns(self, base: dict, extra: dict):
        """将额外规则合并到基础配置中"""
        # 合并操作性语句模式
        if 'operational_patterns' in extra:
            base.setdefault('operational_patterns', [])
            seen = set(base['operational_patterns'])
            for p in extra['operational_patterns']:
                if p not in seen:
                    base['operational_patterns'].append(p)
                    seen.add(p)

        # 合并英文套话模式
        if 'english_platitudes' in extra:
            base.setdefault('english_platitudes', [])
            seen = set(base['english_platitudes'])
            for p in extra['english_platitudes']:
                if p not in seen:
                    base['english_platitudes'].append(p)
                    seen.add(p)

        # 合并高/低价值关键词
        for key in ('high_value_keywords', 'low_value_keywords'):
            if key in extra:
                base.setdefault(key, [])
                seen = set(base[key])
                for kw in extra[key]:
                    if kw not in seen:
                        base[key].append(kw)
                        seen.add(kw)
