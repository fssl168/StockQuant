# -*- coding: utf-8 -*-
"""F020 Phase F1 — 基于 asyncio 的信息处理自动调度器

设计原则：
- 不引入 APScheduler，纯 asyncio 实现
- 支持 4 级调度：realtime（秒级）/ minute（分钟级）/ hourly / daily（指定时刻）
- 单例 PipelineScheduler，FastAPI 启动时 start()，停止时 stop()
- 任务可注入便于测试（pipeline_func 可调用对象）
- 单任务异常不传染其他任务（异常隔离）
- 支持动态添加/移除调度任务
- 日志记录每次执行的耗时、结果摘要、异常

集成方式（FastAPI lifespan）::

    from stockquant.ai.scheduler import get_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = get_scheduler()
        scheduler.bind_pipeline(lambda symbols: pipeline.run(symbols))
        await scheduler.start()
        yield
        await scheduler.stop()

    app = FastAPI(lifespan=lifespan)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.scheduler")


# ── 数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class ScheduleSpec:
    """调度规格

    Attributes:
        name: 任务名（唯一）
        level: 调度级别 realtime|minute|hourly|daily
        interval_seconds: 实时/分钟/小时的间隔秒数
        daily_hour: 日级任务的执行时刻（0-23）
        daily_minute: 日级任务的执行分钟（0-59）
        symbols: 任务参数（要采集的股票代码列表）
        enabled: 是否启用
        last_run_at: 上次执行时间（ISO 字符串）
        last_result: 上次执行结果摘要
        run_count: 累计执行次数
        error_count: 累计错误次数
    """
    name: str
    level: str = "realtime"
    interval_seconds: int = 60
    daily_hour: int = 18
    daily_minute: int = 0
    symbols: List[str] = field(default_factory=list)
    enabled: bool = True
    last_run_at: str = ""
    last_result: str = ""
    run_count: int = 0
    error_count: int = 0


# ── 主调度器 ──────────────────────────────────────────────────────────────


class PipelineScheduler:
    """基于 asyncio 的信息处理调度器

    用法::

        scheduler = PipelineScheduler()
        scheduler.bind_pipeline(my_pipeline_run)
        scheduler.add_task(ScheduleSpec(name="realtime_news", level="realtime", interval_seconds=60))
        await scheduler.start()
        # ...运行中...
        await scheduler.stop()

    测试注入::

        # 测试时替换 pipeline_func，避免真实采集
        scheduler.bind_pipeline(lambda symbols: asyncio.sleep(0.01))
    """

    def __init__(self) -> None:
        self._specs: Dict[str, ScheduleSpec] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._pipeline_func: Optional[Callable[[List[str]], Awaitable[Any]]] = None
        self._running = False

    # ── 配置 ────────────────────────────────────────────────────────────

    def bind_pipeline(self, func: Callable[[List[str]], Awaitable[Any]]) -> None:
        """绑定 pipeline 执行函数

        Args:
            func: 接受 List[str] (symbols) 返回 Awaitable 的协程函数
        """
        self._pipeline_func = func

    def add_task(self, spec: ScheduleSpec) -> None:
        """添加调度任务"""
        if spec.name in self._specs:
            logger.warning("调度任务 %s 已存在，将被覆盖", spec.name)
        self._specs[spec.name] = spec
        if self._running and spec.enabled:
            self._start_task(spec.name)

    def remove_task(self, name: str) -> bool:
        """移除调度任务"""
        if name not in self._specs:
            return False
        self._stop_task(name)
        del self._specs[name]
        return True

    def get_task(self, name: str) -> Optional[ScheduleSpec]:
        return self._specs.get(name)

    def list_tasks(self) -> List[ScheduleSpec]:
        return list(self._specs.values())

    # ── 生命周期 ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """启动所有已配置的调度任务"""
        if self._running:
            logger.warning("调度器已运行，忽略重复 start")
            return
        self._running = True
        logger.info("调度器启动，共 %d 个任务", len(self._specs))
        for name in list(self._specs.keys()):
            spec = self._specs[name]
            if spec.enabled:
                self._start_task(name)

    async def stop(self) -> None:
        """停止所有调度任务"""
        if not self._running:
            return
        self._running = False
        logger.info("调度器停止中...")
        for name in list(self._tasks.keys()):
            self._stop_task(name)
        logger.info("调度器已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 内部任务管理 ────────────────────────────────────────────────────

    def _start_task(self, name: str) -> None:
        """启动单个调度任务的 asyncio.Task"""
        if name in self._tasks and not self._tasks[name].done():
            return
        spec = self._specs[name]
        coro = self._run_loop(spec)
        task = asyncio.create_task(coro, name=f"sched_{name}")
        self._tasks[name] = task
        logger.info("调度任务已启动: %s (level=%s)", name, spec.level)

    def _stop_task(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task and not task.done():
            task.cancel()
            logger.info("调度任务已取消: %s", name)

    async def _run_loop(self, spec: ScheduleSpec) -> None:
        """单个任务的调度循环

        - realtime/minute/hourly: 按 interval_seconds 周期执行
        - daily: 计算下次执行时刻，sleep 到该时刻
        """
        try:
            while self._running and spec.enabled:
                # 计算下次执行时刻
                if spec.level == "daily":
                    wait_seconds = self._seconds_until_next_daily(spec.daily_hour, spec.daily_minute)
                else:
                    wait_seconds = spec.interval_seconds

                # 等待
                try:
                    await asyncio.sleep(wait_seconds)
                except asyncio.CancelledError:
                    break

                if not self._running or not spec.enabled:
                    break

                # 执行
                await self._execute_once(spec)
        except asyncio.CancelledError:
            logger.info("调度任务 %s 被取消", spec.name)
        except Exception as exc:
            logger.exception("调度任务 %s 异常退出: %s", spec.name, exc)

    async def _execute_once(self, spec: ScheduleSpec) -> None:
        """执行一次任务"""
        if self._pipeline_func is None:
            logger.warning("调度任务 %s 跳过：pipeline_func 未绑定", spec.name)
            return

        t_start = datetime.now()
        spec.last_run_at = t_start.isoformat()
        try:
            result = await self._pipeline_func(spec.symbols)
            duration = (datetime.now() - t_start).total_seconds()
            summary = self._summarize_result(result)
            spec.last_result = summary
            spec.run_count += 1
            logger.info(
                "调度任务 %s 完成: 耗时 %.2fs, 结果: %s",
                spec.name, duration, summary[:100],
            )
        except Exception as exc:
            duration = (datetime.now() - t_start).total_seconds()
            spec.error_count += 1
            spec.last_result = f"ERROR: {exc}"
            logger.exception(
                "调度任务 %s 失败: 耗时 %.2fs, %s", spec.name, duration, exc
            )

    # ── 辅助 ────────────────────────────────────────────────────────────

    @staticmethod
    def _seconds_until_next_daily(hour: int, minute: int) -> float:
        """计算距离下次 daily 执行的秒数"""
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    @staticmethod
    def _summarize_result(result: Any) -> str:
        """生成执行结果摘要"""
        if result is None:
            return "None"
        if isinstance(result, dict):
            # 提取关键指标
            parts = []
            for key in ("articles_processed", "filtered_count", "decision_context"):
                if key in result:
                    val = result[key]
                    parts.append(f"{key}={'set' if val else 'empty'}")
            if "insights" in result and isinstance(result["insights"], list):
                parts.append(f"insights={len(result['insights'])}")
            return ", ".join(parts) if parts else str(result)[:200]
        return str(result)[:200]

    # ── 状态查询 ────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """返回调度器状态摘要"""
        return {
            "running": self._running,
            "task_count": len(self._specs),
            "active_tasks": sum(1 for t in self._tasks.values() if not t.done()),
            "tasks": [
                {
                    "name": s.name,
                    "level": s.level,
                    "enabled": s.enabled,
                    "last_run_at": s.last_run_at,
                    "last_result": s.last_result,
                    "run_count": s.run_count,
                    "error_count": s.error_count,
                }
                for s in self._specs.values()
            ],
        }


# ── 单例 ─────────────────────────────────────────────────────────────────


_scheduler_instance: Optional[PipelineScheduler] = None


def get_scheduler() -> PipelineScheduler:
    """获取全局调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = PipelineScheduler()
    return _scheduler_instance


def reset_scheduler() -> None:
    """重置单例（测试用）"""
    global _scheduler_instance
    _scheduler_instance = None
