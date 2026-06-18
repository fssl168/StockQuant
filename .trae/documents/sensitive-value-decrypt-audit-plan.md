# 排查 & 修复：_settings 敏感值未解密问题

## Summary

`ai_chat.py` 中发现并修复了一个关键 Bug：从 `_settings` 字典读取 `api_key` / `api_base` 时，拿到的是 Fernet 加密后的密文，未调用 `_decrypt_value()` 解密就直接传给了 `LLMAdapter`，导致 LLM 调用失败。

本计划的目标是**全面排查项目中所有类似位置**，确保所有从 `_settings` 读取敏感值的地方都正确调用了 `_decrypt_value()`。

---

## Current State Analysis

### 加密机制说明

- **加密入口**: `settings.py` → `save_settings()` 端点 (L648)
  - 当 key 在 `_SENSITIVE_KEYS` 集合中时，保存前自动调用 `_encrypt_value()`
  - 加密后存入 `_settings` 字典 + 持久化到 `~/.stockquant/settings.json`
- **解密函数**: `settings.py` → `_decrypt_value(value)` (L96)
  - 失败时返回原始值（兼容旧明文数据）
- **当前唯一正确使用解密的模块**: `ai_chat.py` (L40-L41)

### `_SENSITIVE_KEYS` 定义 (settings.py:57-67)

```python
_SENSITIVE_KEYS = {
    "ai.api_key", "ai.api_base",
    "evolution.api_key", "evolution.api_base",
    "data_provider.api_key",
    "trading.qmt_password", "trading.xtp_password", "trading.ctp_password",
    "trading.admin_token",
    "notifications.smtp_password",
    "openai_api_key", "anthropic_api_key",
    "redis_password",
    "jwt_secret_key",
}
```

> **注意**: `_SENSITIVE_KEYS` 使用 `trading.xtp_password` 格式（含 `trading.` 前缀），但 `trading.py` 实际读取的 key 是 `xtp.password`（无前缀）。这本身可能是一个 **key 命名不一致的问题**，需确认。

### 排查结果总览

| 文件 | 行号 | 读取的 Key | 是否在 _SENSITIVE_KEYS | 是否调用了 _decrypt_value | 风险等级 |
|------|------|------------|------------------------|--------------------------|---------|
| `ai_chat.py` | 37-38 | `ai.api_key`, `ai.api_base` | ✅ 是 | ✅ **已修复** | — |
| `trading.py` | 94 | `xtp.password` | ⚠️ key名不匹配 | ❌ 未解密 | **高** |
| `trading.py` | 107 | `ctp.password` | ⚠️ key名不匹配 | ❌ 未解密 | **高** |
| `notification.py` | 154 | `notification.telegram_bot_token` | ❌ 不在集合中 | ❌ 未解密 | **中** |
| `notification.py` | 167 | `notification.pushplus_token` | ❌ 不在集合中 | ❌ 未解密 | **中** |
| `notification.py` | 186 | `notification.email_password` | ⚠️ key名不匹配 | ❌ 未解密 | **高** |

### 关于 Webhook URL (dingtalk/wechat/feishu/discord/custom)

这些 URL 本身不是密码/token，但在某些场景下也属于敏感信息（含认证参数）。当前不在 `_SENSITIVE_KEYS` 中，**本次不做修改**，仅记录备查。

---

## Proposed Changes

### Change 1: 修复 `trading.py` — 密码字段未解密

**文件**: `d:\leanpython\StockQuant\stockquant\api\routers\trading.py`

**What**: 在 `_get_broker()` 函数中，对所有密码参数添加 `_decrypt_value()` 调用

**Why**: `xtp.password` 和 `ctp.password` 是券商登录凭证，属于高度敏感信息。如果用户通过 Settings 页面保存过这些配置，它们会被 Fernet 加密存储。不解密直接传入 Broker 构造函数会导致认证失败。

**How**:
1. 在 import 区域添加: `from stockquant.api.routers.settings import _settings, _decrypt_value`
2. L94 行: `password=_settings.get("xtp.password", "")` → `password=_decrypt_value(_settings.get("xtp.password", ""))`
3. L107 行: `password=_settings.get("ctp.password", "")` → `password=_decrypt_value(_settings.get("ctp.password", ""))`

### Change 2: 修复 `notification.py` — Token/Password 未解密

**文件**: `d:\leanpython\StockQuant\stockquant\api\routers\notification.py`

**What**: 在 `_init_notifiers()` 函数中，对 token 和 password 添加 `_decrypt_value()` 调用

**Why**: Telegram bot token、PushPlus token、SMTP password 都是第三方服务凭证。虽然当前它们不在 `_SENSITIVE_KEYS` 集合中（意味着通过 API 保存时不一定被加密），但：
1. 未来可能加入加密集合
2. 如果用户手动编辑 settings.json 或通过其他途径写入加密值，应兼容处理
3. `_decrypt_value()` 对非加密值会原样返回（见 L96-102），所以**无条件调用是安全的**

**How**:
1. 在 import 区域添加: `from stockquant.api.routers.settings import _settings, _decrypt_value`
2. L154 行: `tg_token = _settings.get(...)` → `tg_token = _decrypt_value(_settings.get(...))`
3. L167 行: `pushplus_token = ...` → `pushplus_token = _decrypt_value(...)`
4. L186 行: `password=_settings.get(...)` → `password=_decrypt_value(_settings.get(...))`

### Change 3 (可选): 统一 Key 命名一致性检查

**问题描述**: `_SENSITIVE_KEYS` 定义了 `trading.xtp_password`，但 `trading.py` 读取的是 `xtp.password`。这两个 key 不同，意味着即使 xtp.password 被用户设置，也不会触发加密逻辑（因为 save_settings 只对 `_SENSITIVE_KEYS` 中的 key 加密）。

**建议**: 本次先做 Change 1+2 的防御性解密（反正 `_decrypt_value` 对明文无害）。Key 命名一致性问题作为技术债记录，后续统一重构时可一并解决。

---

## Assumptions & Decisions

1. **`_decrypt_value()` 对明文安全**: 该函数内部 try/except 包裹，对非加密字符串返回原始值，不会破坏正常数据
2. **Webhook URL 不处理**: dingtalk/wechat 等 webhook URL 不在 `_SENSITIVE_KEYS` 中，且通常不含机密信息，暂不处理
3. **evolution 模块**: 如果有其他模块读取 `evolution.api_key` 等，需额外排查（本次范围限 routers 层）

## Verification Steps

1. 重启后端后，检查 uvicorn 启动日志确认 `[main] 已加载 .env`
2. 触发 AI 对话确认仍正常返回（回归验证 Change 0）
3. （可选）在 Settings 页面保存一个测试密码值，然后检查对应模块是否能正确读取
4. 确认所有修改文件的 lint 通过
