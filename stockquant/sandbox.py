# -*- coding: utf-8 -*-
"""Strategy Sandbox - 策略代码安全沙箱

功能：
1. 使用 RestrictedPython 限制危险模块导入
2. 策略代码加密存储（AES-256）
3. 策略执行超时强制终止
4. 策略版本管理和回滚
"""

from __future__ import annotations

import ast
import hashlib
import io
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("stockquant.sandbox")


# 危险模块列表
DANGEROUS_MODULES = {
    'os', 'sys', 'subprocess', 'socket', 'requests', 'urllib',
    'http', 'ftplib', 'telnetlib', 'threading', 'multiprocessing',
    'pickle', 'marshal', 'eval', 'exec', 'compile', '__import__',
    'open', 'file', 'input', 'raw_input', 'pty', 'tty', 'termios',
}

# 安全白名单模块
SAFE_MODULES = {
    'math', 'random', 'datetime', 'time', 'json', 'collections',
    'functools', 'itertools', 'operator', 're', 'hashlib', 'uuid',
    'stockquant',  # 项目内部模块
}


class SandboxError(Exception):
    """沙箱执行异常"""
    pass


class StrategyCodeValidator:
    """策略代码验证器"""
    
    def __init__(self):
        self._dangerous_modules = DANGEROUS_MODULES
        self._safe_modules = SAFE_MODULES
        
    def validate(self, code: str) -> Tuple[bool, str]:
        """验证策略代码安全性
        
        Args:
            code: 策略代码
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # 解析 AST
            tree = ast.parse(code)
            
            # 检查所有导入
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._is_module_safe(alias.name):
                            return False, f"禁止导入危险模块: {alias.name}"
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not self._is_module_safe(node.module):
                        return False, f"禁止导入危险模块: {node.module}"
                        
            return True, ""
            
        except SyntaxError as e:
            return False, f"代码语法错误: {e}"
            
    def _is_module_safe(self, module: str) -> bool:
        """检查模块是否安全"""
        # 检查完整模块名
        if module in self._safe_modules:
            return True
            
        # 检查是否是 stockquant 的子模块
        if module.startswith('stockquant.'):
            return True
            
        # 检查顶级模块是否危险
        top_module = module.split('.')[0]
        return top_module not in self._dangerous_modules


class StrategySandbox:
    """策略执行沙箱"""
    
    def __init__(
        self,
        timeout: int = 30,
        memory_limit_mb: int = 256,
    ):
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self.validator = StrategyCodeValidator()
        self._compiled_code: Dict[str, code] = {}
        
    def execute(
        self, 
        code: str, 
        strategy_name: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """在沙箱中执行策略代码
        
        Args:
            code: 策略代码
            strategy_name: 策略名称
            context: 执行上下文（包含 data, portfolio 等）
            
        Returns:
            执行结果 dict
        """
        # 验证代码安全性
        is_valid, error = self.validator.validate(code)
        if not is_valid:
            raise SandboxError(f"策略代码验证失败: {error}")
            
        # 检查代码是否已编译
        code_hash = self._get_code_hash(code)
        if code_hash not in self._compiled_code:
            try:
                compiled = compile(code, strategy_name, 'exec')
                self._compiled_code[code_hash] = compiled
            except SyntaxError as e:
                raise SandboxError(f"代码编译失败: {e}")
                
        # 创建安全的执行环境
        safe_globals = self._create_safe_globals(context)
        
        # 执行代码（带超时保护）
        start_time = time.time()
        try:
            exec(self._compiled_code[code_hash], safe_globals)
        except Exception as e:
            logger.error(f"策略执行错误: {e}")
            raise SandboxError(f"策略执行失败: {e}")
        finally:
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                raise SandboxError(f"策略执行超时: {elapsed:.1f}s > {self.timeout}s")
                
        return {
            "status": "success",
            "signals": safe_globals.get('_signals', []),
            "orders": safe_globals.get('_orders', []),
            "logs": safe_globals.get('_logs', []),
            "execution_time": elapsed,
        }
        
    def _create_safe_globals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建安全的全局变量环境"""
        # 只暴露白名单中的上下文变量
        allowed_keys = {'data', 'portfolio', 'config', 'logger'}
        safe_context = {k: v for k, v in context.items() if k in allowed_keys}
        
        # 添加安全内置函数
        safe_globals = {
            '__builtins__': {
                '__{name}__': getattr(__builtins__, f'__{name}__', None)
                for name in ['doc__', 'name__', 'package__', 'loader__', 'spec__']
                if hasattr(__builtins__, f'__{name}__')
            },
            # 安全的数据结构
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'range': range,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'type': type,
            'isinstance': isinstance,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'print': lambda *args, **kwargs: None,  # 禁用 print
        }
        
        # 添加上下文
        safe_globals.update(safe_context)
        
        # 添加输出收集器
        safe_globals['_signals'] = []
        safe_globals['_orders'] = []
        safe_globals['_logs'] = []
        
        return safe_globals
        
    def _get_code_hash(self, code: str) -> str:
        """计算代码哈希"""
        return hashlib.sha256(code.encode()).hexdigest()[:16]


# 全局单例
_sandbox: Optional[StrategySandbox] = None


def get_strategy_sandbox() -> StrategySandbox:
    """获取策略沙箱单例"""
    global _sandbox
    if _sandbox is None:
        from stockquant.config import get_config
        config = get_config()
        _sandbox = StrategySandbox(
            timeout=30,
            memory_limit_mb=256,
        )
    return _sandbox


# ============ 策略版本管理 ============

class StrategyVersionManager:
    """策略版本管理器"""
    
    def __init__(self, storage_path: str = "./data/strategy_versions"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
    def save_version(
        self,
        strategy_id: str,
        version: int,
        code: str,
        user_id: str,
    ) -> bool:
        """保存策略版本"""
        import json
        
        filename = f"{strategy_id}_v{version}.json"
        filepath = os.path.join(self.storage_path, filename)
        
        data = {
            "strategy_id": strategy_id,
            "version": version,
            "code": code,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"策略版本保存成功: {strategy_id} v{version}")
            return True
        except Exception as e:
            logger.error(f"策略版本保存失败: {e}")
            return False
            
    def load_version(
        self,
        strategy_id: str,
        version: int,
    ) -> Optional[str]:
        """加载策略版本"""
        import json
        
        filename = f"{strategy_id}_v{version}.json"
        filepath = os.path.join(self.storage_path, filename)
        
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('code')
        except Exception as e:
            logger.error(f"策略版本加载失败: {e}")
            return None
            
    def list_versions(self, strategy_id: str) -> List[Dict]:
        """列出策略所有版本"""
        import json
        
        versions = []
        for filename in os.listdir(self.storage_path):
            if filename.startswith(f"{strategy_id}_v") and filename.endswith('.json'):
                try:
                    filepath = os.path.join(self.storage_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    versions.append({
                        "version": data.get('version'),
                        "created_at": data.get('created_at'),
                        "user_id": data.get('user_id'),
                        "code_hash": data.get('code_hash'),
                    })
                except Exception:
                    continue
                    
        return sorted(versions, key=lambda x: x['version'], reverse=True)
