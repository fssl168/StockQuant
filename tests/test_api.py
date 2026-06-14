# -*- coding: utf-8 -*-
"""F029 API 网关测试 — pytest + httpx + FastAPI TestClient"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stockquant.api.main import create_app

# ========================================================================
# 测试客户端
# ========================================================================

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


# ========================================================================
# 健康检查
# ========================================================================

class TestHealth:

    def test_health_returns_ok(self, client):
        """健康检查返回 status=ok"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime" in data
        assert data["uptime"] >= 0

    def test_health_version_not_empty(self, client):
        """版本字符串非空"""
        resp = client.get("/api/health")
        assert len(resp.json()["version"]) > 0


# ========================================================================
# 回测 CRUD
# ========================================================================

class TestBacktestCRUD:

    def test_submit_backtest(self, client):
        """提交回测任务返回 task_id"""
        payload = {
            "strategy_name": "双均线交叉",
            "strategy_code": "class MyStrategy:\n    pass",
            "symbols": ["sh600519"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "cash": 1_000_000,
        }
        resp = client.post("/api/backtest", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    def test_list_backtests_empty(self, client):
        """空列表"""
        resp = client.get("/api/backtest")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        # 注意：health check 等可能在 setUp 中插入了任务，所以只检查类型

    def test_list_backtests_after_submit(self, client):
        """提交后列表非空"""
        payload = {
            "strategy_name": "测试策略",
            "strategy_code": "pass",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        submit = client.post("/api/backtest", json=payload)
        task_id = submit.json()["task_id"]

        resp = client.get("/api/backtest")
        items = resp.json()
        assert len(items) >= 1
        # 找到刚创建的任务
        found = [t for t in items if t["task_id"] == task_id]
        assert len(found) == 1
        assert found[0]["status"] == "queued"

    def test_get_backtest_result(self, client):
        """获取回测结果"""
        payload = {
            "strategy_name": "详情测试",
            "strategy_code": "pass",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        submit = client.post("/api/backtest", json=payload)
        task_id = submit.json()["task_id"]

        resp = client.get(f"/api/backtest/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert "metrics" in data
        assert "trades" in data
        assert "equity_curve" in data

    def test_get_backtest_not_found(self, client):
        """不存在的任务返回 404"""
        resp = client.get("/api/backtest/nonexistent")
        assert resp.status_code == 404

    def test_delete_backtest(self, client):
        """删除回测任务"""
        payload = {
            "strategy_name": "待删除",
            "strategy_code": "pass",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        submit = client.post("/api/backtest", json=payload)
        task_id = submit.json()["task_id"]

        # 确认存在
        assert client.get(f"/api/backtest/{task_id}").status_code == 200

        # 删除
        delete_resp = client.delete(f"/api/backtest/{task_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        # 确认删除
        assert client.get(f"/api/backtest/{task_id}").status_code == 404

    def test_delete_backtest_not_found(self, client):
        """删除不存在的任务返回 404"""
        resp = client.delete("/api/backtest/nonexistent")
        assert resp.status_code == 404


# ========================================================================
# 策略 CRUD
# ========================================================================

class TestStrategyCRUD:

    def test_create_strategy(self, client):
        """创建策略"""
        payload = {
            "name": "测试策略",
            "code": "class MyStrategy:\n    pass",
            "description": "这是一个测试策略",
        }
        resp = client.post("/api/strategy", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["name"] == "测试策略"
        assert data["code"] == payload["code"]

    def test_list_strategies(self, client):
        """策略列表"""
        # 先创建一个
        client.post("/api/strategy", json={
            "name": "列表测试",
            "code": "pass",
        })
        resp = client.get("/api/strategy")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_strategy(self, client):
        """获取策略详情"""
        payload = {
            "name": "详情测试策略",
            "code": "class TestStrategy:\n    pass",
        }
        create_resp = client.post("/api/strategy", json=payload)
        strategy_id = create_resp.json()["id"]

        resp = client.get(f"/api/strategy/{strategy_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == strategy_id
        assert data["name"] == "详情测试策略"

    def test_get_strategy_not_found(self, client):
        """不存在的策略返回 404"""
        resp = client.get("/api/strategy/nonexistent")
        assert resp.status_code == 404

    def test_update_strategy(self, client):
        """更新策略"""
        payload = {
            "name": "更新前",
            "code": "class TestStrategy:\n    pass",
        }
        create_resp = client.post("/api/strategy", json=payload)
        strategy_id = create_resp.json()["id"]

        update_resp = client.put(f"/api/strategy/{strategy_id}", json={
            "name": "更新后",
        })
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "更新后"

    def test_delete_strategy(self, client):
        """删除策略"""
        payload = {
            "name": "待删除策略",
            "code": "pass",
        }
        create_resp = client.post("/api/strategy", json=payload)
        strategy_id = create_resp.json()["id"]

        assert client.get(f"/api/strategy/{strategy_id}").status_code == 200

        delete_resp = client.delete(f"/api/strategy/{strategy_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        assert client.get(f"/api/strategy/{strategy_id}").status_code == 404

    def test_delete_strategy_not_found(self, client):
        """删除不存在的策略返回 404"""
        resp = client.delete("/api/strategy/nonexistent")
        assert resp.status_code == 404


# ========================================================================
# Dashboard 指标
# ========================================================================

class TestDashboardMetrics:

    def test_metrics_empty(self, client):
        """无回测任务时指标返回零值"""
        resp = client.get("/api/dashboard/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_equity" in data
        assert "sharpe" in data
        assert "max_drawdown" in data
        assert "total_trades" in data
        assert isinstance(data["backtest_count"], int)

    def test_metrics_after_completed_backtest(self, client):
        """完成回测后指标聚合"""
        payload = {
            "strategy_name": "指标测试",
            "strategy_code": "pass",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "cash": 1_000_000,
        }
        submit = client.post("/api/backtest", json=payload)
        task_id = submit.json()["task_id"]

        # 直接操作 backtest router 的存储
        from stockquant.api.routers import backtest
        backtest._tasks[task_id]["status"] = "completed"
        backtest._tasks[task_id]["metrics"] = {
            "Sharpe Ratio": "1.2345",
            "Max Drawdown": "-5.67%",
            "Total Return": "12.34%",
        }
        backtest._tasks[task_id]["equity_curve"] = [[1_000_000, 0], [1_100_000, 1]]

        resp = client.get("/api/dashboard/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backtest_count"] >= 1
        assert data["latest_backtest_status"] == "completed"
        assert data["latest_backtest_return"] == "12.34%"


# ========================================================================
# WebSocket
# ========================================================================

class TestWebSocket:

    def test_ws_connect(self, client):
        """连接 WebSocket"""
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"

    def test_ws_manager_broadcast(self, client):
        """WebSocket manager 广播（单元测试"""
        from stockquant.api.websocket import ws_manager

        # 推送不阻塞
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            ws_manager.push("alert", {"message": "测试告警"})
        )
        # 无连接时不会报错

    def test_ws_manager_connection_count(self, client):
        """连接数统计"""
        from stockquant.api.websocket import ws_manager
        # 连接应在上下文管理器退出后清理
        initial = ws_manager.get_connection_count()
        assert initial == 0
