# StockQuant 100% 达标率最终冲刺计划

> **目标**: 将前端功能与 Product-Spec 对标达标率从 88% 提升至代码层面 100%
> **基准**: `frontend-product-spec-gap-assessment-v2.md` (v3 更新版) + `spec-100percent-completion-plan.md` 执行状态
> **原则**: 自行判断优先级，自行决策，聚焦代码层面可修复的差距；外部依赖项明确标注

---

## 一、当前状态分析

### 已完成项 (F1-F8 + R1)
| # | 任务 | 状态 | 文件 |
|---|------|------|------|
| F1 | Strategy AI 生成策略错误处理 | ✅ | `web/src/pages/Strategy.tsx` |
| F2 | Monitor 动态风控注释更新 | ✅ | `web/src/pages/Monitor.tsx` |
| F3 | Portfolio 移除硬编码 mock | ✅ | `web/src/pages/Portfolio.tsx` |
| F4/F5 | Data 移除 mock + 错误提示 | ✅ | `web/src/pages/Data.tsx` |
| F6 | Optimize 导出/应用按钮实现 | ✅ | `web/src/pages/Optimize.tsx` |
| F7 | Data 下载按钮实现 | ✅ | `web/src/pages/Data.tsx` |
| F8 | notification.py 认证依赖 | ✅ | `stockquant/api/routers/notification.py` |
| R1 | Portfolio 权益快照机制 | ✅ | `stockquant/persistence/models.py` (EquitySnapshot) |

### 剩余代码可修复项
| # | 任务 | 优先级 | 性质 |
|---|------|--------|------|
| R4 | NFR 测试 CI 门控配置 | P3 | 工程规范 |
| R3 | NLP 情感分析模型升级 | P3 | 精度优化 |
| R5 | 本地 HuggingFace 模型推理 | P3 | 性能优化 |
| NFR5 | Sphinx 文档 + 覆盖率量化 | P3 | 可维护性 |
| NFR9 | 真实 LLM 验证测试 | P3 | AI 可靠性 |

### 外部依赖项（非代码可修复，标注说明）
| # | 任务 | 说明 |
|---|------|------|
| R2 | 券商真实 API 下单 | QMT/XTP/CTP 需 SDK 部署和券商授权，骨架代码完整 |
| D7 | Dashboard 实盘持仓聚合 | 需实盘账户接入，非阻塞 |
| M10 | 实时 K 线 Tick 级数据 | A 股 Level-1 行情频率限制，非代码问题 |

---

## 二、实施计划

### Phase 1: R4 — NFR 测试 CI 门控配置

**问题**: 当前 `.github/workflows/test.yml` 第 35 行 NFR 测试用 `|| true` 允许失败，未形成门控。

**修改文件**: `.github/workflows/test.yml`

**修改内容**:
1. 将 NFR 测试从 backend job 中拆分为独立的 `nfr-gate` job
2. 移除 `|| true`，使 NFR 测试成为硬门控
3. 添加 NFR 测试专用 job，允许标记外部服务依赖测试为可选
4. 添加 pytest-json-report 生成测试报告

**具体改动**:
```yaml
# 新增 nfr-gate job
nfr-gate:
  runs-on: ubuntu-latest
  needs: backend  # 在 backend job 之后执行
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
        cache: pip
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    - name: Run NFR tests (hard gate)
      run: |
        pytest tests/test_nfr_performance.py tests/test_nfr_reliability.py -v --tb=short --maxfail=1
    - name: Run NFR AI tests (allow skip for missing API keys)
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        pytest tests/test_nfr_ai_reliability.py -v --tb=short
```

**backend job 修改**:
- 移除第 34-36 行的 NFR 测试步骤（已迁移到 nfr-gate job）
- backend job 仅保留 import check + 单元测试

**验证**: CI pipeline 包含 nfr-gate job，NFR 性能/可靠性测试为硬门控

---

### Phase 2: R3 — NLP 情感分析模型升级

**问题**: `sentiment.py` 已有 HuggingFace 集成代码，但 `transformers` 未在 requirements.txt 中，导致 HuggingFace 分支永不激活。当前模型为通用多语言模型，非中文金融专用。

**修改文件**:
1. `requirements.txt` — 添加 transformers + torch (可选依赖)
2. `stockquant/ai/sentiment.py` — 升级模型 + 优化加载逻辑
3. `tests/test_nfr_ai_reliability.py` — 升级测试使用真实 SentimentAnalyzer

**具体改动**:

#### 2.1 requirements.txt
```
# 在文件末尾添加（可选 AI 增强依赖）
transformers>=4.36  # HuggingFace NLP 模型（情感分析/本地推理）
torch>=2.0  # PyTorch（transformers 后端，CPU 版本即可）
```

#### 2.2 sentiment.py 升级
- 升级模型为中文金融专用: `uer/roberta-base-finetuned-jd-binary-chinese` (京东评论情感，中文金融适用性更好) 或保留 `lxyuan/distilbert-base-multilingual-cased-sentiments-student` 作为多语言备选
- 添加模型加载缓存机制（避免重复加载）
- 添加模型预热（首次调用时预加载）
- 优化 `_analyze_hf` 方法，支持批量文本处理

```python
# 关键改动
_HF_MODEL_NAME = "uer/roberta-base-finetuned-jd-binary-chinese"  # 中文专用
_HF_FALLBACK_MODEL = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"  # 多语言备选

def _try_load_hf_model(self) -> None:
    """尝试加载 HuggingFace 模型（带备选链）"""
    candidates = [self._HF_MODEL_NAME, self._HF_FALLBACK_MODEL]
    for model_name in candidates:
        try:
            from transformers import pipeline
            self._hf_pipeline = pipeline(
                "sentiment-analysis",
                model=model_name,
                top_k=None,
                device=-1,
            )
            self._hf_model_loaded = model_name
            logger.info("HuggingFace 情感模型加载成功: %s", model_name)
            return
        except ImportError:
            logger.info("transformers 未安装，使用增强版关键词规则")
            return
        except Exception as exc:
            logger.warning("HuggingFace 模型 %s 加载失败: %s，尝试备选", model_name, exc)
            continue
```

#### 2.3 test_nfr_ai_reliability.py 升级
- 将 `TestSentimentAnalysis.test_sentiment_accuracy` 改为使用真实 `SentimentAnalyzer` 类
- 添加 `pytest.mark.skipif` 在 transformers 未安装时跳过 HuggingFace 路径测试
- 保留关键词规则测试作为基线

```python
class TestSentimentAnalysis:
    """情感分析准确率 — 目标: ≥75%"""

    def test_sentiment_accuracy_keyword(self):
        """关键词规则基线测试"""
        from stockquant.ai.sentiment import SentimentAnalyzer
        analyzer = SentimentAnalyzer(method="keyword")
        # ... 使用 analyzer.analyze() 替代内联规则

    def test_sentiment_accuracy_huggingface(self):
        """HuggingFace 模型准确率测试（需 transformers）"""
        pytest.importorskip("transformers")
        from stockquant.ai.sentiment import SentimentAnalyzer
        analyzer = SentimentAnalyzer(method="huggingface")
        # ... 验证 HuggingFace 路径准确率
```

**验证**: 
- `transformers` 安装后 SentimentAnalyzer 自动使用 HuggingFace 模型
- 未安装时降级为增强版关键词规则
- NFR 测试覆盖两种路径

---

### Phase 3: R5 — 本地 HuggingFace 模型推理

**问题**: `llm_adapter.py` 仅有 `local_rule_engine` 路径，无 HuggingFace 本地模型推理。NFR008 要求 Tick 级 <200ms，远程 LLM 无法满足。

**修改文件**:
1. `stockquant/agent/llm_adapter.py` — 添加 LocalLLM 适配器
2. `stockquant/config.py` — 添加 local_llm 配置项
3. `stockquant/api/routers/settings.py` — 暴露 local_llm 配置到前端

**具体改动**:

#### 3.1 llm_adapter.py 新增 LocalLLMAdapter
```python
class LocalLLMAdapter:
    """本地 HuggingFace 模型推理适配器
    
    支持:
    1. HuggingFace transformers 本地推理
    2. Ollama 本地服务（通过 HTTP API）
    
    使用方式:
        adapter = LocalLLMAdapter(model="qwen2.5-7b-instruct", backend="ollama")
        response = adapter.call(messages)
    """
    
    def __init__(self, model: str, backend: str = "transformers", 
                 base_url: Optional[str] = None) -> None:
        self._model = model
        self._backend = backend  # "transformers" / "ollama"
        self._base_url = base_url or "http://localhost:11434"
        self._pipeline = None
    
    def _ensure_loaded(self) -> None:
        """懒加载模型"""
        if self._pipeline is not None:
            return
        if self._backend == "transformers":
            try:
                from transformers import pipeline
                self._pipeline = pipeline(
                    "text-generation",
                    model=self._model,
                    device=-1,
                )
            except ImportError:
                raise ImportError("transformers 未安装，无法使用本地推理")
        # ollama 无需预加载，通过 HTTP 调用
    
    def call(self, messages: list[dict], **kwargs) -> LLMResponse:
        """本地模型调用"""
        self._ensure_loaded()
        
        if self._backend == "transformers":
            return self._call_transformers(messages, **kwargs)
        elif self._backend == "ollama":
            return self._call_ollama(messages, **kwargs)
        else:
            raise ValueError(f"不支持的 backend: {self._backend}")
    
    def _call_transformers(self, messages: list[dict], **kwargs) -> LLMResponse:
        """HuggingFace transformers 本地推理"""
        # 合并 messages 为单文本
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        result = self._pipeline(prompt, max_new_tokens=kwargs.get("max_tokens", 512))
        content = result[0]["generated_text"] if result else ""
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            model=f"local/{self._model}",
            finish_reason="stop",
        )
    
    def _call_ollama(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Ollama 本地服务调用"""
        import httpx
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "stream": False,
            },
            timeout=kwargs.get("timeout", 30),
        )
        response.raise_for_status()
        data = response.json()
        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            usage=data.get("prompt_eval_count", {}),
            model=f"ollama/{self._model}",
            finish_reason="stop",
        )
```

#### 3.2 LLMAdapter 集成 LocalLLM
在 `LLMAdapter.call()` 方法中添加 `local_llm` 路径:
```python
def call(self, messages, model=None, **kwargs):
    used_model = model or self._model
    
    # 本地规则引擎路径
    if used_model == "local_rule_engine":
        return self._call_local_rule_engine(messages)
    
    # 本地 LLM 路径（新增）
    if used_model.startswith("local/") or used_model.startswith("ollama/"):
        return self._call_local_llm(messages, used_model, **kwargs)
    
    # 远程 LLM 路径（原有逻辑）
    self._ensure_litellm()
    # ...

def _call_local_llm(self, messages, model, **kwargs):
    """调用本地 LLM 适配器"""
    backend = "ollama" if model.startswith("ollama/") else "transformers"
    model_name = model.split("/", 1)[1]
    adapter = LocalLLMAdapter(model=model_name, backend=backend)
    return adapter.call(messages, **kwargs)
```

#### 3.3 config.py 添加 local_llm 配置
```python
# 在 ai 配置段添加
"local_llm": {
    "enabled": False,
    "backend": "ollama",  # "transformers" / "ollama"
    "model": "qwen2.5-7b-instruct",
    "base_url": "http://localhost:11434",
}
```

#### 3.4 settings.py 暴露配置
在 settings schema 中添加 `ai.local_llm.*` 配置项，前端 Settings 页面可配置。

**验证**:
- `LocalLLMAdapter` 支持 transformers 和 ollama 两种后端
- 模型名以 `local/` 或 `ollama/` 前缀时自动路由到本地推理
- 配置可通过 Settings 页面管理

---

### Phase 4: NFR5 — Sphinx 文档 + 覆盖率量化

**问题**: NFR5 要求测试覆盖率 ≥90% + API 文档，当前无 Sphinx 文档，覆盖率未量化。

**修改文件**:
1. 新建 `docs/sphinx/conf.py` — Sphinx 配置
2. 新建 `docs/sphinx/index.rst` — 文档首页
3. 新建 `docs/sphinx/api.rst` — API 文档
4. 修改 `.github/workflows/test.yml` — 添加覆盖率上报
5. 修改 `requirements.txt` — 添加 sphinx + pytest-cov

**具体改动**:

#### 4.1 Sphinx 文档骨架
```
docs/sphinx/
├── conf.py          # Sphinx 配置（sphinx-rtd-theme）
├── index.rst        # 首页
├── api.rst          # API 自动文档（autodoc）
├── architecture.rst # 架构文档
└── Makefile         # 构建脚本
```

#### 4.2 覆盖率量化
- `.github/workflows/test.yml` 添加 `pytest --cov=stockquant --cov-report=xml`
- 添加覆盖率阈值检查（初始设为 60%，逐步提升至 90%）
- 生成 coverage.xml 供 CI 上报

```yaml
- name: Run tests with coverage
  run: |
    pytest tests/ --cov=stockquant --cov-report=xml --cov-report=term-missing
- name: Check coverage threshold
  run: |
    python -c "import xml.etree.ElementTree as ET; tree = ET.parse('coverage.xml'); rate = float(tree.getroot().attrib['line-rate']); assert rate >= 0.6, f'覆盖率 {rate:.1%} 低于阈值 60%'"
```

**验证**: 
- `docs/sphinx/` 目录存在完整 Sphinx 骨架
- CI 生成覆盖率报告并检查阈值
- `make -C docs/sphinx html` 可构建文档

---

### Phase 5: NFR9 — 真实 LLM 验证测试

**问题**: NFR9 测试用简化数据，未用真实 LLM 验证。

**修改文件**: `tests/test_nfr_ai_reliability.py`

**具体改动**:
- 添加 `TestRealLLMIntegration` 测试类
- 使用 `pytest.mark.skipif` 在无 API key 时跳过
- 测试真实 LLM 调用的反幻觉检查点
- 测试真实 LLM 的事实抽取准确率

```python
class TestRealLLMIntegration:
    """真实 LLM 集成测试（需 API key）"""
    
    @pytest.fixture(autouse=True)
    def _skip_if_no_api_key(self):
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("无 LLM API key，跳过真实 LLM 集成测试")
    
    def test_real_llm_fact_extraction(self):
        """测试真实 LLM 事实抽取"""
        from stockquant.agent.llm_adapter import LLMAdapter
        adapter = LLMAdapter(model="gpt-4o-mini")
        # ... 真实 LLM 调用验证
    
    def test_real_llm_hallucination_detection(self):
        """测试真实 LLM 反幻觉检测"""
        # ... 调用 FiveStepCorrector 验证
```

**验证**: 有 API key 时运行真实 LLM 测试，无 key 时自动跳过

---

### Phase 6: 最终验证

#### 6.1 前端编译验证
```bash
cd web && npx tsc --noEmit
```
预期: 零错误

#### 6.2 后端导入验证
```bash
python -c "import stockquant.api.main; print('Backend import OK')"
```
预期: 输出 "Backend import OK"

#### 6.3 NFR 测试验证
```bash
pytest tests/test_nfr_performance.py tests/test_nfr_reliability.py -v
```
预期: 全部通过

#### 6.4 情感分析验证
```bash
python -c "
from stockquant.ai.sentiment import SentimentAnalyzer
a = SentimentAnalyzer()
r = a.analyze(['利好消息推动股价大涨', '公司业绩暴跌亏损严重'])
print(f'method={r.method}, score={r.score}')
"
```
预期: 输出分析结果（method 为 huggingface 或 enhanced_keyword）

#### 6.5 本地 LLM 适配器验证
```bash
python -c "
from stockquant.agent.llm_adapter import LocalLLMAdapter
adapter = LocalLLMAdapter(model='test', backend='ollama')
print('LocalLLMAdapter 初始化成功')
"
```
预期: 输出 "LocalLLMAdapter 初始化成功"

---

## 三、执行顺序

1. **Phase 1 (R4)**: CI 门控配置 — 最快见效，立即提升工程规范
2. **Phase 2 (R3)**: NLP 情感分析升级 — 添加依赖 + 升级模型
3. **Phase 3 (R5)**: 本地 LLM 推理 — 新增 LocalLLMAdapter
4. **Phase 4 (NFR5)**: Sphinx 文档 + 覆盖率 — 工程规范补全
5. **Phase 5 (NFR9)**: 真实 LLM 测试 — 测试完善
6. **Phase 6**: 最终验证 — 全量检查

---

## 四、验收标准

- [ ] R4: CI pipeline 包含 nfr-gate job，NFR 性能/可靠性测试为硬门控
- [ ] R3: transformers 在 requirements.txt 中，SentimentAnalyzer 支持 HuggingFace 模型
- [ ] R5: LocalLLMAdapter 支持 transformers/ollama 两种后端
- [ ] NFR5: docs/sphinx/ 目录存在，CI 生成覆盖率报告
- [ ] NFR9: 真实 LLM 集成测试存在（无 key 时跳过）
- [ ] 前端 `npx tsc --noEmit` 零错误
- [ ] 后端 `python -c "import stockquant.api.main"` 成功
- [ ] NFR 性能/可靠性测试全部通过

---

## 五、外部依赖项说明（非代码可修复）

以下差距项为外部依赖或数据源限制，代码层面已做到骨架完整，待外部条件具备后即可激活：

| # | 差距项 | 当前状态 | 激活条件 |
|---|--------|---------|---------|
| R2 | 券商真实 API 下单 | QMT/XTP/CTP 三券商骨架完整 | 部署对应 SDK + 券商授权 |
| D7 | Dashboard 实盘持仓聚合 | 后端 API 已支持 | 实盘账户接入 |
| M10 | 实时 K 线 Tick 级数据 | RealtimeKline 组件存在 | A 股 Level-2 行情授权 |

这三项不计入代码层面 100% 达标率范围。
