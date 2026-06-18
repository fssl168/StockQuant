# Plan: AI Chat Page Optimizations

## Summary

Three targeted optimizations to the AI chat page:

1. **Remove duplicate tab bar** — `ChatPanel.tsx` has a second `Segmented` that duplicates `AIChat.tsx`'s. Remove it (single source of truth).
2. **Improve AI reply display** — Add syntax highlighting for code blocks (via `highlight.js`), fix streaming cursor, improve markdown rendering.
3. **Connect frontend persistence to backend** — `aiStore` is completely disconnected from the backend. Messages are lost on refresh/switch. Wire it to the existing backend endpoints.

---

## Current State Analysis

### Tab duplication (AIChat.tsx vs ChatPanel.tsx)

| Location | Line | Modes |
|---|---|---|
| `AIChat.tsx:120-130` | `Segmented` | general, strategy, analysis, monitor, **decision**, indicator (6) |
| `ChatPanel.tsx:322-334` | `Segmented` | general, strategy, analysis, monitor, indicator (5, missing `decision`) |

`ChatPanel` also accepts `mode` + `onModeChange` props and re-emits the same segmented bar. Both control the same state (`mode` in `AIChat`). This is redundant and inconsistent (missing `decision` in child).

### AI reply display issues (ChatPanel.tsx)

- **No syntax highlighting** — code blocks rendered as plain `<pre><code>`, no colors. `highlight.js` not in `package.json`.
- **Minimal streaming cursor** — only a `|` character with CSS blink, no animated dots or thinking indicator.
- **Code blocks not isolated** — code in `<div dangerouslySetInnerHTML>` lacks monospace font or distinct styling.
- `ChatPanel.tsx` already parses `chart-json` blocks and renders ECharts — this is good and should be preserved.

### Conversation persistence gap (aiStore.ts)

```
Frontend: aiStore (Zustand, NO persistence)
  - conversations list → only in memory
  - messages → only in memory
  - createConversation → generates UUID, saves to memory only
  - switchConversation → clears messages, never loads from backend
  - addMessage → never calls backend API

Backend: ChatAgent + ChatMemory
  - /ai/chat (POST) → saves message via ChatMemory (DB or in-memory)
  - /ai/chat/stream (POST) → SSE streaming, also saves via ChatMemory
  - /ai/conversations (GET) → returns conversation list from ChatMemory
  - /ai/conversation/{id} (GET) → returns message history
  - /ai/conversation/{id} (DELETE) → clears conversation
```

The backend endpoints exist and work. The frontend just never calls them. On page reload → all messages gone. On switch conversation → messages cleared (not loaded from backend).

---

## Proposed Changes

### Change 1: Remove duplicate tab bar — `web/src/components/AI/ChatPanel.tsx`

**What:** Remove the redundant `Segmented` bar from `ChatPanel.tsx:322-334`. Remove `mode` and `onModeChange` props from `ChatPanelProps` interface (lines 80-81). Remove the prop usage at line 324 (`onChange` → remove) and the subtitle text (lines 335-337).

**Why:** Single source of truth for the mode state lives in `AIChat.tsx`. The child tab bar is redundant and inconsistent (missing `decision` mode).

**Before:**
```tsx
<Segmented
  value={mode}
  onChange={(v) => onModeChange?.(v as string)}
  options={[
    { label: '默认', value: 'general' },
    { label: '策略开发', value: 'strategy' },
    { label: '数据分析', value: 'analysis' },
    { label: '盯盘', value: 'monitor' },
    { label: '指标发现', value: 'indicator' },
  ]}
  size="small"
  style={{ marginBottom: 12 }}
/>
<Text type="secondary" style={{ marginBottom: 16, fontSize: 12 }}>
  与 AI 量化助手对话，探索策略、分析数据、解读回测结果
</Text>
```

**After:** Remove both elements entirely. The `ChatPanel` no longer needs to know about mode — it just renders messages.

Also update `ChatPanelProps` interface (lines 75-82) to remove `mode` and `onModeChange`:
```tsx
interface ChatPanelProps {
  messages: Message[]
  streamingContent?: string
  isStreaming?: boolean
  onSend: (message: string) => void
}
```

And update `AIChat.tsx` to stop passing these props (lines 141-142):
```tsx
<ChatPanel
  messages={...}
  streamingContent={streamingContent}
  isStreaming={isStreaming}
  onSend={handleSend}
/>
```

### Change 2: Improve AI reply display — `web/src/components/AI/ChatPanel.tsx`

**What:** Add `highlight.js` for syntax highlighting and improve streaming display.

**Why:** Code blocks currently render without color. Adding syntax highlighting makes AI code responses much more readable. Also improve the streaming "thinking" indicator.

**Steps:**

**Step 2a:** Add `highlight.js` to dependencies.
```sh
cd web && npm install highlight.js
```

**Step 2b:** In `ChatPanel.tsx`, configure `marked` to use `highlight.js` for fenced code blocks. Add after the existing `marked.setOptions`:

```ts
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

marked.setOptions({
  breaks: true,
  gfm: true,
})
// 注册 highlight.js 作为代码高亮器
const renderer = new marked.Renderer()
renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
}
marked.use({ renderer })
```

Also update the `renderMarkdown` function to return highlighted HTML:

```ts
function renderMarkdown(content: string): string {
  return DOMPurify.sanitize(marked.parse(content) as string)
}
```

(Note: `marked.parse` is the newer API replacing direct `marked(content)` call.)

**Step 2c:** Fix the streaming display (lines 457-478) — replace minimal `|` cursor with animated thinking dots and a pulsing background:

```tsx
{isStreaming && (
  <List.Item style={{ paddingTop: 12, paddingBottom: 12, borderBottom: '1px solid var(--color-bg-surface)', borderRadius: 4 }}>
    <List.Item.Meta
      avatar={<Avatar style={{ background: 'var(--color-brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28 }}>
        <ChatCircleText size={16} weight="fill" />
      </Avatar>}
      title={<Text strong style={{ fontSize: 12, color: 'var(--color-text-primary)' }}>AI 助手</Text>}
      description={
        streamingContent ? (
          <div
            style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)' }}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingContent) }}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <div className="thinking-dots" style={{ display: 'flex', gap: 4 }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--color-brand-primary)',
                  animation: `thinking-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
            <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>正在思考...</span>
          </div>
        )
      }
    />
  </List.Item>
)}
```

Add CSS animation to the `<style>` block at the bottom:
```css
@keyframes thinking-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
```

**Step 2d:** Fix user message rendering (line 427-431) — add `renderMarkdown` to user messages so markdown in user input also renders:
```tsx
<div
  style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
/>
```

### Change 3: Connect aiStore to backend persistence — `web/src/stores/aiStore.ts`

**What:** Wire `aiStore` to backend endpoints so conversations and messages persist across page reloads and conversation switches.

**Backend endpoints already exist:**
- `GET /ai/conversations` → `{conversations: [{id, title, created_at, message_count}]}`
- `GET /ai/conversation/{id}` → `{conversation_id, messages: [{role, content, timestamp}]}`
- `POST /ai/conversation/{id}` → creates/updates conversation
- `DELETE /ai/conversation/{id}` → clears conversation

**Changes to `web/src/api/ai.ts`:**
```ts
export const aiApi = {
  // ...existing...
  getConversations: () => client.get('/ai/conversations') as Promise<{
    conversations: { id: string; title: string; created_at: string; message_count: number }[]
  }>,
  getConversation: (id: string) => client.get(`/ai/conversation/${id}`) as Promise<{
    conversation_id: string
    messages: { role: string; content: string; timestamp: string }[]
  }>,
  deleteConversation: (id: string) => client.delete(`/ai/conversation/${id}`) as Promise<void>,
}
```

**Changes to `web/src/stores/aiStore.ts`:**

Restructure the store to:
1. On initialization (first load): fetch conversation list from backend
2. `addMessage`: also call backend (via `streamChat` already does this, so backend gets the message)
3. `createConversation`: save to backend after creating
4. `switchConversation`: load messages for that conversation from backend
5. Persist `conversations` and `activeConversationId` to `localStorage` for fast restore before backend fetch

New store structure:
```ts
export const useAIStore = create<AIState>((set, get) => ({
  messages: [],
  conversations: [],
  activeConversationId: '',
  isLoaded: false,  // NEW: tracks whether we've fetched from backend

  // On app init: try to restore from localStorage, then fetch from backend
  init: async () => {
    // Restore last active conversation from localStorage
    try {
      const saved = localStorage.getItem('ai_state')
      if (saved) {
        const { conversations, activeConversationId } = JSON.parse(saved)
        if (conversations?.length > 0 && activeConversationId) {
          set({ conversations, activeConversationId, messages: [] })
        }
      }
    } catch { /* ignore */ }

    // Fetch from backend
    try {
      const data = await aiApi.getConversations()
      const convs = (data.conversations || []).map((c: any) => ({
        id: c.id,
        title: c.title,
        createdAt: c.created_at ? new Date(c.created_at).getTime() : Date.now(),
        messageCount: c.message_count ?? 0,
      }))
      const state = get()
      const activeId = state.activeConversationId || convs[0]?.id || ''
      set({ conversations: convs, activeConversationId: activeId, isLoaded: true })

      // Load messages for active conversation
      if (activeId) {
        const msgData = await aiApi.getConversation(activeId)
        const msgs = (msgData.messages || []).map((m: any) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.timestamp ? new Date(m.timestamp).getTime() : Date.now(),
        }))
        set({ messages: msgs })
      }
    } catch {
      const state = get()
      set({ isLoaded: true, activeConversationId: state.activeConversationId || crypto.randomUUID() })
    }
  },

  addMessage: (role, content) => {
    set((st) => {
      const newMessages = [...st.messages, { role, content, timestamp: Date.now() }]
      // Save to localStorage for fast restore
      const convs = st.conversations.map(c =>
        c.id === st.activeConversationId
          ? { ...c, messageCount: c.messageCount + 1, title: c.title || (role === 'user' ? content.slice(0, 20) : c.title) }
          : c
      )
      // Persist to localStorage
      try {
        localStorage.setItem('ai_state', JSON.stringify({
          conversations: convs,
          activeConversationId: st.activeConversationId,
        }))
      } catch { /* ignore */ }
      return { messages: newMessages, conversations: convs }
    })
  },

  createConversation: () => {
    const state = get()
    const newId = crypto.randomUUID()
    set({ activeConversationId: newId, messages: [], conversations: [...state.conversations] })
    try {
      localStorage.setItem('ai_state', JSON.stringify({
        conversations: state.conversations,
        activeConversationId: newId,
      }))
    } catch { /* ignore */ }
  },

  switchConversation: async (id) => {
    // Save current conversation's title if it has messages but no title
    const state = get()
    const updatedConvs = state.conversations.map(c =>
      c.id === state.activeConversationId && c.messageCount > 0 && !c.title
        ? { ...c, title: state.messages[0]?.content?.slice(0, 20) || '新对话' }
        : c
    )

    set({ activeConversationId: id, messages: [], conversations: updatedConvs })
    try {
      localStorage.setItem('ai_state', JSON.stringify({
        conversations: updatedConvs,
        activeConversationId: id,
      }))
    } catch { /* ignore */ }

    // Load messages for new conversation from backend
    try {
      const msgData = await aiApi.getConversation(id)
      const msgs = (msgData.messages || []).map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: m.timestamp ? new Date(m.timestamp).getTime() : Date.now(),
      }))
      set({ messages: msgs })
    } catch { /* ignore */ }
  },
}))
```

**Changes to `AIChat.tsx`:**
- Import `aiApi`
- Call `useAIStore.getState().init()` on mount (inside `useEffect`)
- Also update `conversations` prop type since `createdAt` is now a `number` (not `string`)

**Changes to `AIChat.tsx` conversation list rendering:**
The `createdAt` in the store is now a timestamp `number`. Fix the date rendering:
```tsx
{new Date(conv.createdAt).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}
```
(This is already correct in the current code — just verify it uses `conv.createdAt` not `conv.created_at`.)

**Note on `clear()`:** The `clear` method in the current store is not connected to any UI button. If there's a "clear conversation" button, it should call `aiApi.deleteConversation(id)` before clearing local state.

---

## Out of scope (explicitly NOT changing)

- Backend `ChatAgent` and `ChatMemory` — working fine, no changes needed
- The `chart-json` block parsing in `ChatPanel` — already working well
- `SignalCard` detection and display — already working
- The `ai.ts` `streamChat` function — already connects to backend correctly
- Backend API routes in `ai_chat.py` — already exist and working

---

## Assumptions & Decisions

1. **Persistence uses backend as source of truth + localStorage as fast cache.** On init: restore from localStorage (instant), then fetch from backend (async). This gives fast perceived load while keeping data synced.
2. **`createdAt` in store is a Unix timestamp `number`** (via `Date.now()`), consistent with other stores in the codebase (e.g., `backtestStore`). The `created_at` from backend is ISO string → converted on load.
3. **No `persist` middleware for Zustand** — the app already has inconsistent patterns (some stores use `localStorage` directly, some don't). Using direct `localStorage` reads/writes in the relevant actions keeps it simple and consistent with the existing `aiStore` style.
4. **highlight.js theme** — using `github-dark.css` as it matches the dark theme of the app.
5. **marked API** — using `marked.parse()` (not the deprecated direct call). `marked` v15 API.

---

## Verification

1. **`tsc -b`** — no new type errors from added `aiApi` methods and store changes.
2. **Tab bar:** Refresh AI chat page — only one `Segmented` bar should be visible (in `AIChat`, not in `ChatPanel`).
3. **Syntax highlighting:** Ask AI to generate Python code — code block should be colored with `highlight.js` styles.
4. **Streaming:** Send a message and watch streaming — animated bouncing dots + "正在思考..." should appear before content starts streaming.
5. **Persistence:** 
   - Open AI chat, send 2-3 messages
   - Refresh the page → messages should reappear (loaded from backend + localStorage cache)
   - Create a new conversation, send messages
   - Switch back to first conversation → messages should load from backend
