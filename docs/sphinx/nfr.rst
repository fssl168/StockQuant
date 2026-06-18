非功能需求 (NFR)
================

NFR001 性能
-----------

* 回测速度 ≥ 5000 Bar/s（日线）
* 缓存读取 < 100ms
* 指标计算 < 1ms/次
* 风控检查 < 1ms/订单
* WebSocket 推送 < 500ms

测试: ``tests/test_nfr_performance.py``

NFR002 可靠性
-------------

* 事件零丢失
* 幂等订单（idempotency_key）
* 崩溃恢复（JSON 持久化 + 启动恢复）
* 回测确定性（random.seed）

测试: ``tests/test_nfr_reliability.py``

NFR004 安全性
-------------

* JWT 4 级认证（current/required/admin/trader）
* API Key Fernet 加密存储
* CORS 环境变量配置
* 角色权限（ADMIN/TRADER/VIEWER）

NFR005 可维护性
---------------

* 测试覆盖率 ≥ 60%（CI 门控，目标 90%）
* FastAPI 自动 Swagger 文档
* Sphinx API 文档（``docs/sphinx/``）

NFR008 AI 性能与成本
--------------------

* 采集延迟 < 5min
* 决策延迟 < 3s
* Tick 级 < 200ms（本地 LLM 推理）
* 日成本 ≤ 2 元

实现: ``LocalLLMAdapter`` 支持 HuggingFace/Ollama 本地推理

NFR009 AI 可靠性
----------------

* 事实验证 ≥ 99%
* 幻觉检出 ≥ 80%
* 情感分析准确率 ≥ 75%

测试: ``tests/test_nfr_ai_reliability.py``
