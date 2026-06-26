# 输出模板（PRFAQ / PRD / 设计系统）

## PRFAQ 模板（约 1000 字）

### Press Release（对外发布稿）

- 产品名称（暂定）：
- 一句话价值主张：
- 面向谁（目标用户）：
- 解决的核心问题：
- 关键差异化（为何更好）：
- 核心功能亮点（3–5 条）：
- 关键体验亮点（3–5 条，聚焦 UI/UX）：
- 可访问性与包容性承诺（1 段）：
- 性能与稳定性承诺（1 段）：
- 引用（虚拟用户/团队成员的一句话，不使用 emoji）：

### FAQ（至少覆盖以下问题）

1. 这是什么？解决什么场景？
2. 目标用户是谁？不适合谁？
3. 为什么现在做？不做会怎样？
4. 典型用户旅程是什么？最短路径是什么？
5. 成功如何衡量？核心指标是什么？
6. 关键风险与对策（产品/设计/技术/内容）？
7. 边界与不做什么（明确拒绝范围）？
8. 无障碍与动效策略是什么？
9. 迁移与发布策略（如何避免影响现有用户）？

## 需求清单模板（洞察后补齐隐性需求）

建议以表格输出：

| 类别 | 需求 | 用户价值 | 触发场景 | 优先级（MoSCoW） | 备注 |
|---|---|---|---|---|---|
| 功能 |  |  |  |  |  |
| 内容 |  |  |  |  |  |
| 体验 |  |  |  |  |  |
| 可访问性 |  |  |  |  |  |
| 性能/稳定性 |  |  |  |  |  |

## PRD 模板

### 1. 背景与目标

- 背景问题：
- 目标用户：
- 目标（可量化）：
- 非目标：

### 2. 用户与场景

- 用户角色（至少 3 类）：
- 关键场景：
- 核心任务路径（Happy path + 分支）：

### 3. 需求与优先级（MoSCoW）

- Must：
- Should：
- Could：
- Won't：

### 4. 信息架构

- Sitemap（站点地图）：用缩进列表表达
- Task Flow（任务流）：用步骤编号表达（含分支）

### 5. 页面与组件

对每个页面/模块说明：
- 页面目标与主要信息层级
- 组件清单
- 状态（默认/悬停/激活/禁用/错误/空态/加载）
- 校验与错误文案策略（若含表单）

### 6. 数据结构与约束

- 关键字段、单位、精度、默认值
- 排序/过滤/分页/权限约束
- 与现有后端接口的对齐点

### 7. 可访问性、响应式与动效规范

- 可访问性：对比度、焦点、键盘路径、ARIA（仅在必要时）
- 响应式：三断点策略、表格/图表小屏策略
- 动效：200–300ms、prefers-reduced-motion 回退

### 8. 验收标准

- 关键路径可用性验收
- 视觉一致性与可读性
- 响应式与触控可用性
- 性能与稳定性底线

## Design Tokens 模板（CSS Variables 示例）

```css
:root {
  color-scheme: light dark;

  --bg: #0b0c0f;
  --panel: #11131a;
  --text: #e9eaf0;
  --muted: rgba(233, 234, 240, 0.72);

  --brand: #d7ff2f;
  --brand-2: #00d1ff;

  --danger: #ff4d4d;
  --warning: #ffcc00;
  --success: #2fe38f;

  --border: rgba(233, 234, 240, 0.14);
  --shadow: 0 18px 50px rgba(0, 0, 0, 0.35);

  --radius-1: 10px;
  --radius-2: 16px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI",
    "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
    "Noto Sans SC", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
}
```
