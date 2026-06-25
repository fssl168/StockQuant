
## 二、重构目标

### 2.1 目标

1. **数据层统一**: 合并 persistence/ 三层冗余, 建立单一的 Repository 层
2. **AI层标准化**: 统一 LLM 调用接口, 标准化 AI 配置管理
3. **数据库模型优化**: 消除重复表, 统一订单/持仓模型
4. **前后端类型对齐**: 前端自动从后端 schema 生成类型, 消除手动维护

### 2.2 约束

- 不删除任何功能, 只做架构重组
- 保持所有现有 API 路由路径不变 (向后兼容)
- 数据库通过 Alembic 迁移, 不删表
- Redis 不可用时降级为内存缓存
- 前端 API 路由不变, 只适配字段名

### 2.3 成功标准

- 数据访问从3层降为2层 (ORM + Repository)
- 新增一个数据源只需实现一个 Provider class
- 新增一个 LLM 提供商只需在 config 加一行 + 实现一个 Adapter
- 前端类型零手动维护 (自动从 OpenAPI 生成)
- 数据库无重复表, 订单生命周期一个表覆盖

---

## 三、重构方案 (9个阶段)

### Phase 0: 影响面分析 (Day 0)

**目标**: 确认所有引用点, 避免遗漏

| 操作 | 命令 |
|------|------|
| 全局搜索 EventType | g -l "EventType" |
| 全局搜索 persistent_store | g -l "persistent_store" |
| 全局搜索 repository | g -l "from stockquant.persistence.repository" |
| 全局搜索 LLMAdapter | g -l "LLMAdapter\|LocalLLMAdapter" |
| 全局搜索 PendingOrder | g -l "PendingOrder" |
| 前端API调用映射 | web/src/api/ 下所有文件 |

**产出**: 依赖关系图, 影响文件清单

---

### Phase 1: 统一事件系统 (1天)

**问题**: events.py 的 EventType 与 models/order.py 的 OrderStatus 两套枚举并存

**改动**:

1. **合并 EventType**, 新增:
   - ORDER_SUBMITTED (合并 PENDING/SUBMITTED)
   - ORDER_PARTIAL_FILL (新增)
   - ORDER_CANCELLED (已有)
   - ORDER_REJECTED (已有)
   - POSITION_CLOSED (新增)
   - ACCOUNT_BALANCE_UPDATE (拆分 ACCOUNT_UPDATE)

2. **删除 models/order.py 的 OrderStatus**, 统一用 EventType 中的订单状态

3. **更新所有引用**:
   - persistence/models.py: Order.status 字段默认值
   - persistence/repository.py: list_orders 的 status 过滤
   - api/routers/trading.py: 订单状态判断
   - 前端 types/index.ts: OrderStatus 类型

**文件清单**:
- stockquant/events.py - 扩展 EventType
- stockquant/models/order.py - 删除 OrderStatus, 迁移使用 EventType
- stockquant/persistence/models.py - Order.status 默认值调整
- web/src/types/index.ts - OrderStatus 类型对齐

---

### Phase 2: 扩展配置层 (1天)

**问题**: config.py 无 AI/LLM 配置, 数据源配置不够结构化

**改动**:

`python
# config.py 新增配置类

class LLMProviderSettings(BaseModel):
    """单个 LLM 提供商配置"""
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 60

class AISettings(BaseSettings):
    """AI 统一配置"""
    enabled: bool = True
    orchestrator_mode: str = "sequential"  # sequential | parallel | fallback
    default_provider: str = "openai"
    
    # 多提供商支持
    openai: Optional[LLMProviderSettings] = None
    anthropic: Optional[LLMProviderSettings] = None
    local_model: Optional[LLMProviderSettings] = None
    
    # Agent 配置
    max_concurrent_agents: int = 3
    agent_timeout: int = 30
    hallucination_check: bool = True
    hallucination_threshold: float = 0.3

class DataProviderSettings(BaseModel):
    """重构: 结构化数据源配置"""
    default_source: str = "alphafeed"
    
    # 每个 provider 独立配置
    alphafeed: Optional[dict] = None
    baostock: dict = Field(default_factory=lambda: {"enabled": True})
    tushare: Optional[dict] = None
    tdx: Optional[dict] = None
    duckdb: Optional[dict] = None
    csv: Optional[dict] = None
`

**文件清单**:
- stockquant/config.py - 新增 AISettings + 重构 DataProviderSettings

---

### Phase 3: 新建DataService (2天)

**问题**: 数据获取分散在 Provider + repository + persistent_store 中, 无统一入口

**改动**:

新建 stockquant/data/service.py:

`python
class DataService:
    """统一数据服务层"""
    
    def __init__(self, config: Settings):
        self._providers: Dict[str, BaseProvider] = {}
        self._cache: Dict[str, Any] = {}
        self._repo = Repository(config.database.url)
        self._register_default_providers()
    
    def get_kline(self, symbol: str, timeframe: str, 
                  start: str, end: str, source: str = None) -> List[BarData]:
        """统一K线获取: 先查缓存 -> 查DB -> 调Provider"""
        cache_key = f"kline:{symbol}:{timeframe}:{start}:{end}"
        
        # 1. 内存缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 2. 数据库查询
        bars = self._repo.get_kline_db(symbol, timeframe, start, end)
        if bars:
            self._cache[cache_key] = bars
            return bars
        
        # 3. 调Provider获取并持久化
        provider = self.get_provider(source)
        bars = provider.fetch_kline(symbol, timeframe, start, end)
        if bars:
            self._repo.save_kline_db(bars)
            self._cache[cache_key] = bars
        
        return bars
    
    def get_provider(self, name: str) -> BaseProvider:
        return self._providers[name]
    
    def register_provider(self, name: str, provider: BaseProvider): ...
`

**改造 DataFeed**:
- DataFeed 保留作为引擎兼容层
- DataFeed 内部委托 DataService

**文件清单**:
- stockquant/data/service.py - 新建
- stockquant/data/feed.py - 改造为委托 DataService
- stockquant/data/providers/ - Provider 增加 get_supported_symbols()
- stockquant/api/main.py - 注入 DataService 实例

---

### Phase 4: 新建AIService (1天)

**问题**: AI 调用散落在 12个 Agent 模块中, LLM 配置硬编码

**改动**:

新建 stockquant/ai/service.py:

`python
class AIService:
    """统一AI服务层"""
    
    def __init__(self, config: Settings):
        self._adapters: Dict[str, BaseLLMAdapter] = {}
        self._register_adapters()
        self._default = config.ai.default_provider
    
    def get_adapter(self, provider: str = None) -> BaseLLMAdapter:
        provider = provider or self._default
        return self._adapters[provider]
    
    async def chat(self, messages: List[Dict], provider: str = None, **kwargs) -> str:
        adapter = self.get_adapter(provider)
        return await adapter.chat(messages, **kwargs)
    
    async def generate_strategy(self, description: str) -> str:
        """AI生成策略代码 (统一入口)"""
        adapter = self.get_adapter()
        prompt = self._build_strategy_prompt(description)
        return await adapter.chat([{"role": "user", "content": prompt}])
    
    async def check_hallucination(self, content: str) -> Dict:
        """幻觉检测 (统一入口)"""
        adapter = self.get_adapter("openai")  # 始终用大模型检测
        prompt = self._build_hallucination_prompt(content)
        return await adapter.chat([{"role": "user", "content": prompt}])
`

**改造 LLMAdapter**:
- llm_adapter.py 的 LLMAdapter 继承 BaseLLMAdapter
- 从 config.ai.{provider} 读取配置, 不再硬编码
- 新增 BaseLLMAdapter ABC 定义统一接口

**文件清单**:
- stockquant/ai/service.py - 新建
- stockquant/agent/llm_adapter.py - 改造, 从 config 读配置
- stockquant/ai/orchestrator.py - 使用 AIService 而非直接构造 LLMAdapter
- 所有 Agent 模块 - 通过 AIService 获取 LLM 能力

---

### Phase 5: 仓储层合并 (2天)

**问题**: repository.py (100+函数) + persistent_store.py (8个Store类) 重复

**改动**:

新建 stockquant/persistence/repository_v2.py:

`python
class Repository:
    """统一仓储层 - 合并 repository.py + persistent_store.py"""
    
    def __init__(self, db_url: str, cache_ttl: int = 300):
        self._engine = get_engine(db_url)
        self._session_factory = sessionmaker(self._engine)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = cache_ttl
    
    # ������ CRUD 方法
    async def get_backtest(self, user_id: str, result_id: int) -> Optional[dict]:
        cache_key = f"bt:{user_id}:{result_id}"
        cached = self._get_cache(cache_key)
        if cached: return cached
        
        with self._session() as session:
            result = session.query(BacktestResult).filter_by(
                user_id=user_id, id=result_id
            ).first()
        data = self._result_to_dict(result)
        self._set_cache(cache_key, data)
        return data
    
    async def list_backtests(self, user_id: str, limit: int = 50) -> List[dict]:
        ...
    
    # 策略 CRUD
    async def save_strategy(self, ...) -> str:
        ...
    async def list_strategies(self, user_id: str) -> List[dict]:
        ...
    
    # 订单 CRUD
    async def save_order(self, order: Order) -> str:
        ...
    async def list_orders(self, user_id: str, status: str = None) -> List[dict]:
        ...
    
    # 持仓 CRUD
    async def save_position(self, position: Position) -> bool:
        ...
    async def list_positions(self, user_id: str) -> List[dict]:
        ...
    
    # 用户认证
    async def get_user(self, user_id: str) -> Optional[dict]:
        ...
    async def save_user(self, ...) -> str:
        ...
    
    # AI 记忆
    async def save_l2_memory(self, ...) -> str:
        ...
    async def search_l3_memory(self, query: str, top_k: int = 5) -> List[dict]:
        ...
    
    # 缓存管理
    def _get_cache(self, key: str): ...
    def _set_cache(self, key: str, data: dict): ...
    def clear_cache(self): ...
`

**策略**:
- 保留 epository.py 作为兼容层, 内部委托给 Repository
- 删除 persistent_store.py 中的 Store 类 (功能已合并)
- 迁移引用: 路由层 -> Repository, 新代码 -> Repository

**文件清单**:
- stockquant/persistence/repository_v2.py - 新建
- stockquant/persistence/repository.py - 改造为委托
- stockquant/persistence/persistent_store.py - 标记废弃
- 所有路由文件 - 逐步切换到 Repository

---

### Phase 6: 订单模型统一 (1天)

**问题**: PendingOrder + Order + OrderAudit 三表重叠, 下单流程复杂

**改动**:

1. **保留三张表**, 明确职责:
   - orders: 完整订单生命周期 (PENDING -> SUBMITTED -> PARTIAL_FILLED -> FILLED/CANCELLED/REJECTED)
   - order_audits: 订单操作日志 (下单、撤单、改价)
   - **删除 pending_orders**: 功能并入 orders 表

2. **Alembic 迁移**:
   - 标记 pending_orders 表为 deprecated
   - orders 表增加 roker_order_id 字段
   - orders 表增加 illed_quantity, vg_fill_price 字段

3. **Repository 改造**:
   - 删除所有 pending_order_* 函数
   - 所有下单操作通过 save_order() 写入 orders 表

**文件清单**:
- stockquant/persistence/models.py - 删除 PendingOrder, 扩展 Order
- stockquant/persistence/repository.py - 删除 pending_order_* 函数
- stockquant/persistence/repository_v2.py - 同上
- stockquant/api/routers/trading.py - 适配新接口
- Alembic migration - 新增迁移脚本

---

### Phase 7: 路由层适配 (2天)

**改动**: 所有路由文件从 Repository 读取数据, 不再直接操作 Engine

**逐个文件适配**:
- uth.py -> Repository.get_user/save_user
- acktest.py -> Repository.get_backtest/save_backtest
- strategy.py -> Repository.get_strategy/save_strategy
- 	rading.py -> Repository.save_order/list_orders
- portfolio.py -> Repository.list_positions/get_trading_account
- data.py -> DataService.get_kline
- i_chat.py -> AIService.chat
- memory.py -> Repository.save_l2_memory/search_l3_memory
- 其余路由同理

**文件清单**: 21个路由文件全部适配

---

### Phase 8: 前端配套改造 (2天)

**问题**: 前端手动维护 TypeScript 类型, 与后端 schema 不一致; snake_case 到 camelCase 转换在运行时做

**改动**:

#### 8.1 引入 openapi-typescript-codegen

`ash
npm install -D openapi-typescript-codegen
`

配置 openapi-config.json:
`json
{
  "input": "http://localhost:8000/openapi.json",
  "output": "./src/generated",
  "prefixParamaters": true,
  "exportModelDefinitionsExport":"true",
  "schemas": "./*.ts"
}
`

#### 8.2 删除手动类型定义

- 删除 web/src/types/index.ts 中已被 OpenAPI 生成的类型
- 保留业务类型: BrokerMode, OrderSide, OrderType, OrderStatus (前端特有)

#### 8.3 清理 axios 拦截器

`	ypescript
// client.ts - 简化
const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = \Bearer \
  return config
})

// 删除 snakeToCamel 转换 - 让后端 Pydantic 直接返回 camelCase
client.interceptors.response.use(
  (r) => r.data,  // 直接返回, 不做 key 转换
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
    }
    return Promise.reject(new Error(error.response?.data?.detail || error.message))
  }
)
`

#### 8.4 后端 Pydantic schema 改造

所有 Pydantic Model 使用 alias 返回 camelCase:

`python
class BacktestResult(BaseModel):
    task_id: str = Field(alias="taskId")
    strategy_name: str = Field(alias="strategyName")
    equity_curve: List = Field(alias="equityCurve")
    
    model_config = ConfigDict(
        populate_by_name=True,  # 同时支持蛇形和驼峰
    )
`

#### 8.5 Stores 适配

- 	radingStore.ts: 字段名从 snake_to_camel 结果改为直接使用 camelCase
- acktestStore.ts: 同上
- iStore.ts: 同上
- dataStore.ts: 同上
- uthStore.ts: 同上
- 
otificationStore.ts: 同上

**文件清单**:
- web/src/api/client.ts - 删除 snakeToCamel, 简化拦截器
- web/src/types/index.ts - 保留前端特有类型, 删除与后端重复的类型
- web/src/stores/*.ts - 字段名适配
- web/src/generated/ - 新增 (自动生成的类型)
- 所有 web/src/components/ 和 web/src/pages/ - 字段名适配

---

### Phase 9: 测试与验证 (1天)

**后端测试**:
`ash
# 类型检查
mypy stockquant/

# 单元测试
pytest stockquant/tests/ -v

# 接口健康检查
curl http://localhost:8000/api/health
`

**前端验证**:
`ash
cd web
npm run build  # 确保无类型错误
npm run test   # 确保测试通过
`

---

## 四、数据流全景图

### 重构后架构

`
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React + TypeScript)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ API层    │ │ Stores   │ │ 组件     │ │ 生成类型     │   │
│  │(axios)   │ │(Zustand) │ │ (30+)    │ │(OpenAPI)    │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
└───────┼────────────┼────────────┼───────────────┼───────────┘
        │            │            │               │
        ▼            ▼            ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI (后端)                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   路由层 (21 routers)                    │  │
│  │  auth │ backtest │ strategy │ trading │ portfolio │ ...  │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                       │
│              ┌────────▼────────┐                              │
│              │  DataService    │ ← Phase 3 新建                │
│              │  - get_kline    │                              │
│              │  - get_provider │                              │
│              └────────┬────────┘                              │
│                       │                                       │
│              ┌────────▼────────┐                              │
│              │  AIService      │ ← Phase 4 新建                │
│              │  - chat         │                              │
│              │  - generate     │                              │
│              └────────┬────────┘                              │
│                       │                                       │
│              ┌────────▼────────┐                              │
│              │  Repository     │ ← Phase 5 合并               │
│              │  - CRUD 统一入口  │                              │
│              └────────┬────────┘                              │
│                       │                                       │
│         ┌─────────────┼─────────────┐                         │
│         ▼             ▼             ▼                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ SQLite   │  │ PostgreSQL│  │   Redis   │                    │
│  │ (开发)   │  │ (生产)   │  │ (缓存)   │                    │
│  └──────────┘  └──────────┘  └──────────┘                    │
└──────────────────────────────────────────────────────────────┘

         ┌──────────────────────────────────────┐
         │        外部数据源层                    │
         │  BaoStock │ Tushare │ AlphaFeed │ ... │
         └──────────────────────────────────────┘
         
         ┌──────────────────────────────────────┐
         │        AI 服务层                       │
         │  OpenAI │ Anthropic │ 本地模型 │ ...   │
         └──────────────────────────────────────┘
`

---

## 五、数据库迁移方案

### Alembic 迁移步骤

1. **init**: lembic init stockquant/migrations
2. **migration_1**: 删除 pending_orders 相关约束, 扩展 orders 表
   - ALTER TABLE orders ADD COLUMN broker_order_id VARCHAR(64)
   - ALTER TABLE orders ADD COLUMN filled_quantity INTEGER DEFAULT 0
   - ALTER TABLE orders ADD COLUMN avg_fill_price FLOAT DEFAULT 0.0
3. **migration_2**: JSONB 迁移 (PostgreSQL)
   - backtest_results.metrics TEXT -> JSONB
   - backtest_results.equity_curve TEXT -> JSONB
4. **migration_3**: 新增索引
   - orders: (user_id, status) 复合索引
   - positions: (user_id, symbol) 唯一约束
5. **migration_4**: 清理废弃表标记

---

## 六、风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 兼容性问题 (旧路由引用) | 中 | 高 | 保留旧 repository.py 作为适配层 |
| Redis 不可用 | 低 | 中 | 内存缓存自动降级 |
| 前端类型不匹配 | 中 | 中 | OpenAPI 自动生成, 编译时捕获 |
| 迁移数据丢失 | 低 | 高 | Alembic 迁移前备份, 回滚脚本 |
| 性能下降 | 低 | 中 | 缓存层保留, 压测验证 |

---

## 七、实施时间表

| 阶段 | 天数 | 关键交付物 |
|------|------|-----------|
| Phase 0: 影响面分析 | 0.5 | 依赖关系图, 文件清单 |
| Phase 1: 事件系统统一 | 1 | EventType 扩展, OrderStatus 迁移 |
| Phase 2: 配置层扩展 | 1 | AISettings, 重构 DataProviderSettings |
| Phase 3: DataService 新建 | 2 | service.py, DataFeed 改造 |
| Phase 4: AIService 新建 | 1 | service.py, llm_adapter 改造 |
| Phase 5: 仓储层合并 | 2 | repository_v2.py, 路由适配 |
| Phase 6: 订单模型统一 | 1 | 删除 pending_orders, 迁移脚本 |
| Phase 7: 路由层适配 | 2 | 21个路由文件全部适配 |
| Phase 8: 前端改造 | 2 | OpenAPI 生成, 类型对齐 |
| Phase 9: 测试验证 | 1 | 通过所有测试 |
| **合计** | **~13.5天** | |

---

## 八、关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 保留旧 repository.py? | 是, 作为适配层 | 避免全量替换导致的生产风险 |
| 删除 persistent_store.py? | 标记废弃, 保留文件 | 不影响运行, 给团队过渡时间 |
| 前端类型手动维护还是自动生成? | 自动生成 | 消除维护成本, 保证一致性 |
| snake_case 还是 camelCase? | 后端返回 camelCase | 前端原生使用, 减少转换 |
| PendingOrder 表保留? | 删除, 功能并入 Order | 职责重叠, 增加复杂度 |
| Redis 降级策略? | 内存 dict 缓存 | 简单可靠, 不影响核心功能 |
