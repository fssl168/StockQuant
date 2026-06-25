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


# ====================================================================
# 用户认证
# ====================================================================

class UserToken(BaseModel):
    """JWT 声明结构（解码后的 token payload）"""

    sub: str = Field(..., description="用户标识", examples=["user-001"])
    roles: List[str] = Field(default_factory=list, description="用户角色列表")
    role: str = Field(..., description="主角色", examples=["ADMIN"])


class TokenRefreshRequest(BaseModel):
    """刷新 token 请求"""

    refresh_token: str = Field(..., description="当前有效 token", min_length=1)


class TokenRefreshResponse(BaseModel):
    """Token 刷新响应"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


class UserInfoResponse(UserToken):
    """用户信息响应"""

    roles: List[str]


class RegisterRequest(BaseModel):
    """用户注册请求"""

    username: str = Field(..., description="用户名", min_length=3, max_length=50)
    password: str = Field(..., description="密码", min_length=8)
    role: str = Field(default="TRADER", description="角色")


# ====================================================================
# 通知
# ====================================================================

class NotificationItem(BaseModel):
    """通知项"""

    id: str = ""
    type: str = "info"  # info | warning | error | success
    title: str = ""
    message: str = ""
    time: str = ""
    read: bool = False


# ====================================================================
# 盯盘
# ====================================================================

class MonitorAlertItem(BaseModel):
    """盯盘告警项"""

    id: str = ""
    symbol: str = ""
    direction: str = ""  # BUY | SELL | HOLD
    reason: str = ""
    confidence: float = 0.0
    signal_type: str = ""
    is_portfolio_hold: bool = False
    created_at: str = ""


class MonitorStatusResponse(BaseModel):
    """盯盘状态响应"""

    running: bool = False
    alert_count: int = 0
    symbol_count: int = 0
    threshold: float = 0.5


class PremarketBriefingResponse(BaseModel):
    """盘前简报响应"""

    date: str = ""
    signals: List[Dict[str, Any]] = Field(default_factory=list)


class PostmarketSummaryResponse(BaseModel):
    """盘后摘要响应"""

    date: str = ""
    summary: str = ""


class SentimentAnalysisResponse(BaseModel):
    """情绪分析响应"""

    symbol: str = ""
    sentiment: str = ""
    score: float = 0.0


class RiskControlResponse(BaseModel):
    """风控参数响应"""

    max_position_pct: float = 0.3
    max_buy_amount: float = 500000.0
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.15


# ====================================================================
# 交易
# ====================================================================

class OrderCreateRequest(BaseModel):
    """下单请求"""

    symbol: str = Field(..., description="标的代码", examples=["sh600519"])
    side: str = Field(..., description="方向: buy | sell", examples=["buy"])
    order_type: str = Field(..., description="类型: market | limit", examples=["market"])
    price: Optional[float] = Field(default=None, description="限价（仅 limit 订单）")
    quantity: int = Field(..., description="数量", ge=1)


class OrderResponse(BaseModel):
    """下单结果响应"""

    order_id: str
    status: str
    symbol: str
    side: str
    price: float = 0.0
    quantity: int = 0


class PositionItem(BaseModel):
    """持仓项"""

    symbol: str = ""
    quantity: int = 0
    available_quantity: int = 0
    cost_price: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


class TradeItem(BaseModel):
    """成交项"""

    trade_id: str = ""
    symbol: str = ""
    side: str = ""
    price: float = 0.0
    quantity: int = 0
    amount: float = 0.0
    timestamp: str = ""


class OrderListItem(BaseModel):
    """订单列表项"""

    order_id: str = ""
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    price: float = 0.0
    quantity: int = 0
    filled_quantity: int = 0
    status: str = ""
    created_at: str = ""


class AccountSummaryResponse(BaseModel):
    """账户摘要"""

    total_equity: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0


# ====================================================================
# 策略对比
# ====================================================================

class ComparisonRequest(BaseModel):
    """策略对比请求"""

    strategy_ids: List[str] = Field(..., description="策略 ID 列表", min_length=2)
    symbol: str = Field(default="sh600519", description="对比标的")
    start_date: str = Field(default="2023-01-01", description="开始日期")
    end_date: str = Field(default="2024-12-31", description="结束日期")


class ComparisonHistoryEntry(BaseModel):
    """对比历史记录"""

    id: str = ""
    strategy_ids: str = ""
    result: Optional[Dict[str, Any]] = None
    created_at: str = ""


class ComparisonResult(BaseModel):
    """对比结果"""

    comparison_id: str = ""
    strategies: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation: str = ""


class OptimizationResult(BaseModel):
    """组合优化结果"""

    portfolio: Dict[str, Any] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)


# ====================================================================
# 信号管线
# ====================================================================

class SignalAddRequest(BaseModel):
    """添加信号请求"""

    symbol: str = Field(..., description="标的", examples=["sh600519"])
    direction: str = Field(..., description="方向", examples=["BUY"])
    reason: str = Field(..., description="信号原因")
    confidence: Optional[float] = Field(default=0.5, description="置信度", ge=0, le=1)


# ====================================================================
# 数据管理
# ====================================================================

class DataSourceUpdateRequest(BaseModel):
    """数据源配置更新请求"""

    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据源类型")
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    is_active: bool = True


class CacheStatsResponse(BaseModel):
    """缓存统计"""

    total_records: int = 0
    size_mb: float = 0.0
    oldest_record: Optional[str] = None
    newest_record: Optional[str] = None


# ====================================================================
# 参数优化
# ====================================================================

class OptimizeRequest(BaseModel):
    """参数优化请求"""

    strategy_id: str = Field(..., description="策略 ID")
    symbol: str = Field(default="sh600519", description="标的")
    start_date: str = Field(default="2023-01-01")
    end_date: str = Field(default="2024-12-31")
    param_grid: Dict[str, Any] = Field(default_factory=dict, description="参数搜索空间")


class OptimizeStatusResponse(BaseModel):
    """优化任务状态"""

    task_id: str
    status: str
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None


# ====================================================================
# 投资组合
# ====================================================================

class SectorAllocationItem(BaseModel):
    """行业分配项"""

    sector: str = ""
    allocation: float = 0.0
    value: float = 0.0


class PnlAnalysisResponse(BaseModel):
    """盈亏分析"""

    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0


class EquityCurveResponse(BaseModel):
    """权益曲线"""

    points: List[List] = Field(default_factory=list, description="[[timestamp, equity], ...]")
    start_equity: float = 0.0
    end_equity: float = 0.0


class RiskMetricsResponse(BaseModel):
    """风控指标"""

    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0


# ====================================================================
# 审计日志
# ====================================================================

class AuditLogItem(BaseModel):
    """审计日志项"""

    id: int = 0
    user_id: str = ""
    timestamp: str = ""
    signal_source: str = ""
    symbol: str = ""
    direction: str = ""
    final_action: str = ""
    ai_decision: str = ""


# ====================================================================
# 调度器
# ====================================================================

class TaskInfoResponse(BaseModel):
    """定时任务信息"""

    name: str = ""
    cron_expr: str = ""
    is_running: bool = False
    from_db: bool = False


class SchedulerStatusResponse(BaseModel):
    """调度器状态"""

    running: bool = False
    task_count: int = 0
    task_names: List[str] = Field(default_factory=list)


# ====================================================================
# AI 对话扩展
# ====================================================================

class ChatResponse(BaseModel):
    """AI 对话响应"""

    reply: str = ""
    model: str = ""
    usage: Optional[Dict[str, Any]] = None


class ConversationsListResponse(BaseModel):
    """会话列表"""

    sessions: List[Dict[str, Any]] = Field(default_factory=list)


class ConversationDetailResponse(BaseModel):
    """会话详情"""

    session_id: str = ""
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class MarketDataResponse(BaseModel):
    """市场数据查询结果"""

    symbol: str = ""
    data: List[Dict[str, Any]] = Field(default_factory=list)


class NewsSearchResponse(BaseModel):
    """新闻搜索结果"""

    keyword: str = ""
    results: List[Dict[str, Any]] = Field(default_factory=list)


class StrategyGeneratedResponse(BaseModel):
    """生成的策略"""

    strategy_name: str = ""
    strategy_code: str = ""
    description: str = ""


# ====================================================================
# 仪表盘
# ====================================================================

class DashboardSignal(BaseModel):
    """仪表盘信号项"""

    symbol: str = ""
    direction: str = ""
    reason: str = ""
    confidence: float = 0.0
    timestamp: str = ""


# ====================================================================
# 设置
# ====================================================================

class SettingsSaveRequest(BaseModel):
    """设置保存请求"""

    settings: Dict[str, Any] = Field(default_factory=dict, description="设置键值对")


class SettingsResponse(BaseModel):
    """设置响应"""

    settings: Dict[str, Any] = Field(default_factory=dict)


class SourcesResponse(BaseModel):
    """可用配置源响应"""

    sources: Dict[str, str] = Field(default_factory=dict, description="配置来源映射")


# ====================================================================
# 扩展：回测（补充缺失字段）
# ====================================================================

class BacktestRequestExtended(BaseModel):
    """扩展回测请求（包含策略类和额外参数）"""

    strategy_name: str = Field(..., description="策略名称", examples=["双均线交叉"])
    strategy_code: str = Field(..., description="策略 Python 代码")
    symbols: List[str] = Field(default_factory=list, description="标的列表", examples=["sh600519", "sz000858"])
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", examples=["2023-01-01"])
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", examples=["2024-12-31"])
    cash: float = Field(default=1_000_000.0, description="初始资金", ge=0)
    commission_type: CommissionType = Field(default=CommissionType.ASHARE, description="佣金类型")
    slippage_type: SlippageType = Field(default=SlippageType.NONE, description="滑点类型")
    # 扩展字段（原 BacktestRequest 缺失）
    strategy_class: Optional[str] = None
    strategy_params: Optional[Dict[str, Any]] = None
    commission_rate: Optional[float] = None
    min_commission: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    transfer_fee_rate: Optional[float] = None
    benchmark: Optional[str] = None


# ====================================================================
# 新增：类型标注完善用 Pydantic 模型（2026-06-21 Round 3）
# ====================================================================


class ChatRequest(BaseModel):
    """AI 对话请求"""
    message: str = Field(..., description="用户消息")
    conversation_id: str = Field(default="default", description="会话 ID")
    mode: str = Field(default="general", description="对话模式")


class SaveMessageRequest(BaseModel):
    """保存消息请求"""
    role: str = Field(default="user", description="角色")
    content: str = Field(..., description="消息内容")


class GenerateStrategyRequest(BaseModel):
    """生成策略请求"""
    description: str = Field(..., description="策略描述")
    strategy_type: str = Field(default="trend", description="策略类型")


class ComparePaperBacktestRequest(BaseModel):
    """模拟盘 vs 回测对比请求"""
    backtest_id: str = Field(..., description="回测任务 ID")
    paper_equity: List[float] = Field(default_factory=list, description="模拟盘权益曲线")
    backtest_equity: List[float] = Field(default_factory=list, description="回测权益曲线")


class CompareStrategiesRequest(BaseModel):
    """策略对比请求"""
    strategy_ids: List[str] = Field(..., description="回测任务 ID 列表", min_length=2)


class PlaceOrderRequest(BaseModel):
    """下单请求"""
    symbol: str = Field(..., description="股票代码")
    side: str = Field(default="BUY", description="买卖方向")
    type: str = Field(default="MARKET", description="订单类型")
    price: float = Field(default=0.0, description="价格")
    quantity: int = Field(default=0, description="数量")
    idempotency_key: Optional[str] = Field(default=None, description="幂等键")


class StartMonitoringRequest(BaseModel):
    """开始盯盘请求"""
    symbols: Optional[List[str]] = Field(default=None, description="监控标的")


class UpdateDataRequest(BaseModel):
    """更新数据源配置请求"""
    provider: str = Field(..., description="数据源名称")


class CollectDataRequest(BaseModel):
    """采集数据请求"""
    symbol: str = Field(..., description="股票代码")
    source: str = Field(default="alphafeed", description="数据源")
    start: str = Field(default="", description="开始日期")
    end: str = Field(default="", description="结束日期")


class AddSignalRequest(BaseModel):
    """添加信号请求"""
    symbol: str = Field(..., description="股票代码")
    side: str = Field(default="HOLD", description="方向")
    source: str = Field(default="AI_DECISION", description="信号来源")
    confidence: float = Field(default=0.5, description="置信度")
    reason: str = Field(default="", description="理由")
    price: Optional[float] = Field(default=None, description="价格")
    quantity: Optional[int] = Field(default=None, description="数量")
