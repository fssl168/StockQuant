# -*- coding: utf-8 -*-
"""F029 Pydantic 数据模型 — 请求/响应类型定义"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ====================================================================
# 回测相关
# ====================================================================

class CommissionType(str, Enum):
    佣金类型 = "commission_type"
    ASHARE = "ashare"
    FIXED = "fixed"
    NONE = "none"


class SlippageType(str, Enum):
    滑点类型 = "slippage_type"
    FIXED = "fixed"
    PERCENT = "percent"
    NONE = "none"


class BacktestRequest(BaseModel):
    """提交回测任务的请求"""

    strategy_name: str = Field(..., description="策略名称", examples=["双均线交叉"])
    strategy_code: str = Field(..., description="策略 Python 代码")
    symbols: List[str] = Field(default_factory=list, description="标的列表", examples=["sh600519", "sz000858"])
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", examples=["2023-01-01"])
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", examples=["2024-12-31"])
    cash: float = Field(default=1_000_000.0, description="初始资金", ge=0)
    commission_type: CommissionType = Field(default=CommissionType.ASHARE, description="佣金类型")
    slippage_type: SlippageType = Field(default=SlippageType.NONE, description="滑点类型")


class BacktestResult(BaseModel):
    """回测任务结果"""

    task_id: str
    status: str  # queued / running / completed / failed
    strategy_name: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict, description="回测指标")
    trades: List[Dict[str, Any]] = Field(default_factory=list, description="交易明细")
    equity_curve: List[List] = Field(default_factory=list, description="权益曲线")
    error: Optional[str] = None


# ====================================================================
# 策略相关
# ====================================================================

class StrategyCreate(BaseModel):
    """创建策略的请求"""

    name: str = Field(..., description="策略名称", min_length=1, max_length=200)
    code: str = Field(..., description="策略 Python 代码", min_length=1)
    description: str = Field(default="", description="策略描述", max_length=1000)


class StrategyInfo(BaseModel):
    """策略信息"""

    id: str
    name: str
    code: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


# ====================================================================
# 数据源相关
# ====================================================================

class DataSourceConfig(BaseModel):
    """数据源配置"""

    name: str = Field(..., description="数据源名称", examples=["BaoStock"])
    type: str = Field(..., description="数据源类型", examples=["baostock", "tushare", "csv"])
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    is_active: bool = True


# ====================================================================
# Dashboard 相关
# ====================================================================

class DashboardMetrics(BaseModel):
    """仪表盘核心指标"""

    total_equity: float = 0.0
    daily_pnl: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    backtest_count: int = 0
    latest_backtest_status: str = ""
    latest_backtest_return: str = ""


# ====================================================================
# 通用响应
# ====================================================================

class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "ok"
    version: str = ""
    uptime: float = 0.0


class TaskResponse(BaseModel):
    """通用任务响应"""

    task_id: str
    status: str


class MessageResponse(BaseModel):
    """通用消息响应"""

    success: bool = True
    message: str = ""


class WebSocketMessage(BaseModel):
    """WebSocket 消息格式"""

    type: str  # progress | metrics | trade | alert | quote
    data: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    timestamp: str = Field(default_factory=datetime.now().isoformat)


# ====================================================================
# AI 对话相关
# ====================================================================

class AIChatRequest(BaseModel):
    """AI 对话请求"""

    message: str = Field(..., description="用户消息", min_length=1)
    context: Optional[Dict[str, Any]] = None
