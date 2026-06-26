# 前端硬性规范（落地到代码时逐条自检）

## HTML 与语义

- 使用 HTML5 语义结构：header / main / aside / section / nav / footer
- 标题层级正确：每页一个 h1，向下递进，不跳级
- 表单元素有 label；图片有 alt；交互控件可键盘操作

## meta 与基础 Head

- 必备 meta：
  - viewport：`<meta name="viewport" content="width=device-width, initial-scale=1">`
  - color-scheme：`<meta name="color-scheme" content="light dark">`

## 字体（CDN + 中英文混排）

- 通过 CDN 引入 Google Fonts（示例：Inter）
- 提供中英文混排备用字体栈（系统字 + 常见中文字体）

示例（可按项目栈调整引入方式）：

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

## 图标（不要 emoji）

- 优先使用内联 SVG 图标（可自行绘制简单几何符号/图标）
- 或使用 Font Awesome CDN（若项目允许/需要）
- 也可选用 Lucide / Heroicons / Tabler Icons（仅在项目已在用或你能以纯 SVG 方式引入时）

## 响应式与触控

- 至少三断点（示例：≤640 / 641–1024 / ≥1025）
- 可点击区域不小于 44×44px
- 表格与图表必须有小屏策略：
  - 表格：横向滚动（sticky 首列/表头可选）或卡片化折叠列
  - 图表：缩略 + 关键指标优先，必要时切换为列表/迷你图

## 动效与可访问性

- 动效时长 200–300ms（hover/focus/入场/滚动反馈）
- 必须支持 prefers-reduced-motion：

```css
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
```

- 焦点可见：`:focus-visible` 明确且对比度足够
- 对比度达标：正文与背景、按钮与背景、边框与背景

## 图片（必须真实链接，不留空白占位）

需要图片时必须给出实际可访问链接，不要写 “TODO/placeholder/待补充”。

推荐使用 Picsum（示例）：
- 固定尺寸：`https://picsum.photos/800/600`
- 指定 id：`https://picsum.photos/id/870/800/600`
- 避免缓存（同尺寸多图）：`https://picsum.photos/800/600?random=1`
- 灰度/模糊组合：`https://picsum.photos/id/870/800/600?grayscale&blur=2`
- 指定格式：`https://picsum.photos/800/600.webp` 或 `https://picsum.photos/800/600.jpg`

## 主题偏好

- 避免常见的“千篇一律紫色或纯蓝主色”
- 优先使用更具辨识度的中性色或高品质品牌色，并保证可读性
