# Plan: Fix WS Connection Failure + Add Token Passing to useWebSocket

## Summary

The user's hypothesis ("WS fails because backend needs token auth") is **half right**: `useWebSocket` indeed never sends a token, but the backend's `if token:` guard makes the token **optional**, so missing token is *not* the actual cause of failure. The real root cause is a misconfigured Vite proxy: the `/ws` entry uses `target: 'ws://localhost:8000'`, but Vite's underlying `http-proxy` expects an **HTTP** target (`http://localhost:8000`) — the `ws://` scheme breaks the WS upgrade handshake, causing all `/ws/*` connections to fail.

This plan does two things:
1. **Fix the real root cause** — correct the Vite proxy `/ws` target scheme.
2. **Add token passing to `useWebSocket`** — matches the user's original intent, enables authenticated WS, and future-proofs against any later backend tightening of the `if token:` guard.

## Current State Analysis

### Vite proxy — `web/vite.config.ts` (lines 24-37)
```ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',   // ✅ correct HTTP scheme
      changeOrigin: true,
      ws: true,
    },
    '/ws': {
      target: 'ws://localhost:8000',     // ❌ wrong scheme — http-proxy expects http://
      ws: true,                          // ⚠️ missing changeOrigin (inconsistent with /api)
    },
  },
},
```
**Problem:** Vite uses `http-proxy` under the hood. The `target` field must be an HTTP(S) URL; the `ws: true` flag tells http-proxy to also proxy WS upgrade requests on that HTTP target. Using `ws://` as the target scheme causes the proxy to mis-handle the WS upgrade, so all `/ws/*` connections fail. This is the systemic cause affecting **all** WS endpoints (notification, monitor, backtest, chat, optimize).

### `useWebSocket` hook — `web/src/hooks/useWebSocket.ts` (lines 35-88)
- Lines 40-49: builds `wsUrl` from relative path (handles `VITE_WS_URL` env or `${proto}//${host}${url}`).
- Line 50: `const ws = new WebSocket(wsUrl)` — passes the bare URL, **no token attached**.
- No import of auth store, no `localStorage` read, no `?token=` append anywhere.
- Three call sites all pass bare paths: `AppLayout.tsx:49` (`/ws/notification`), `Monitor.tsx:88-90` (`/ws/monitor`), `Backtest.tsx:51-53` (`/ws/backtest/${taskId}`).

### Backend WS endpoints — `stockquant/api/main.py` (lines 96-257)
- Six endpoints registered at `/ws`, `/ws/notification`, `/ws/monitor`, `/ws/backtest/{task_id}`, `/ws/chat/{conversation_id}`, `/ws/optimize/{task_id}`.
- Token check pattern (e.g. lines 113-121 for `/ws/notification`):
  ```python
  token = websocket.query_params.get("token")
  if token:
      try:
          jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
      except Exception:
          await websocket.close(code=4001, reason="invalid token")
          return
  ```
  → Missing token = anonymous allowed. Invalid token = close 4001. Valid token = authenticated.
- Expected token format: **JWT as `?token=<jwt>` query param** (browser `WebSocket` API cannot set Authorization headers, so query param is the only viable transport).

### Token storage convention — `web/src/api/client.ts` (lines 22-28)
```ts
function getToken(): string | null {
  try { return localStorage.getItem('auth_token') } catch { return null }
}
```
JWT persisted under `localStorage` key `auth_token`. Same key used by `authStore.ts`.

## Proposed Changes

### Change 1: Fix Vite proxy `/ws` target scheme — `web/vite.config.ts` (lines 32-35)

**What:** Change the `/ws` proxy entry's `target` from `ws://localhost:8000` to `http://localhost:8000`, and add `changeOrigin: true` for consistency with the `/api` entry.

**Before:**
```ts
'/ws': {
  target: 'ws://localhost:8000',
  ws: true,
},
```

**After:**
```ts
'/ws': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  ws: true,
},
```

**Why:** `http-proxy` (Vite's proxy engine) requires an HTTP target. The `ws: true` flag handles the WS upgrade on that HTTP target. Using `ws://` as the target scheme is the root cause of all WS connection failures. Adding `changeOrigin` matches the `/api` entry and avoids Host-header mismatch with the backend.

**How:** Single edit to lines 32-35 of `web/vite.config.ts`. Requires Vite dev server restart to take effect.

### Change 2: Add token passing to `useWebSocket` — `web/src/hooks/useWebSocket.ts` (lines 40-50)

**What:** After building `wsUrl` (line 49) and before `new WebSocket(wsUrl)` (line 50), read the JWT from `localStorage.auth_token` and append it as `?token=<jwt>` (or `&token=<jwt>` if the URL already has a query string).

**Before (lines 40-50):**
```ts
let wsUrl = url
if (url.startsWith('/')) {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) {
    wsUrl = `${envUrl}${url}`
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${proto}//${window.location.host}${url}`
  }
}
const ws = new WebSocket(wsUrl)
```

**After:**
```ts
let wsUrl = url
if (url.startsWith('/')) {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) {
    wsUrl = `${envUrl}${url}`
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    wsUrl = `${proto}//${window.location.host}${url}`
  }
}
// 附加 JWT token 以通过后端 WS 端点的 token 校验（后端 ?token= 查询参数）
try {
  const token = localStorage.getItem('auth_token')
  if (token) {
    wsUrl += (wsUrl.includes('?') ? '&' : '?') + `token=${encodeURIComponent(token)}`
  }
} catch { /* ignore localStorage access errors */ }
const ws = new WebSocket(wsUrl)
```

**Why:**
- Backend WS endpoints validate `?token=` if present; passing it enables authenticated connections (so server-side logic that branches on `current_user` works correctly).
- Future-proofs against any later tightening of the `if token:` guard to mandatory auth.
- Uses `encodeURIComponent` to safely encode the JWT (which contains `.` separators; while `.` is URL-safe, encoding is defensive and correct).
- Reuses the same `auth_token` localStorage key as `client.ts` — single source of truth for the JWT.
- Wrapped in try/catch to mirror `client.ts`'s defensive `getToken()` pattern (localStorage can throw in private-mode/sandboxed contexts).

**How:** Single edit to `web/src/hooks/useWebSocket.ts`, inserting the token-append block between the existing URL-build block and the `new WebSocket(wsUrl)` call. No new imports needed (uses bare `localStorage`). No changes to the three call sites — they keep passing bare paths; the hook centralizes token attachment.

### Out of scope (explicitly NOT changing)
- Backend `if token:` guard in `main.py` — kept as optional to preserve anonymous fallback.
- The three `useWebSocket` call sites — no token logic leaks into callers.
- `docs/backend-ws-audit.md` — stale (claims WS endpoints live in router modules with `/api/ws/*` prefixes; actual code registers them on the app at `/ws/*`). Not touching docs in this task.
- `VITE_WS_URL` env handling — left as-is.

## Assumptions & Decisions

1. **Root cause is the Vite proxy target scheme.** The `ws://` target is the most likely systemic cause because it affects *all* `/ws/*` endpoints uniformly, matching the user's report that "all /ws endpoints fail". The token gap, while real, would not cause failures given the backend's optional-token behavior.
2. **Token read directly from `localStorage`** rather than importing a helper from `client.ts` or the auth store. Rationale: `client.ts`'s `getToken` is not exported (it's a private function), and importing the auth store would couple a low-level hook to a Zustand store. Direct `localStorage.getItem('auth_token')` matches the existing convention in `client.ts` and `Settings.tsx:217-219` and keeps the hook dependency-free.
3. **Token passed as query param** — the only viable transport, since the browser `WebSocket` API cannot set `Authorization` headers. This matches what the backend already expects (`websocket.query_params.get("token")`).
4. **No backend changes** — the `if token:` optional guard is preserved. If the user later wants mandatory WS auth, that's a separate task (would need to change the guard to reject missing tokens and verify all WS callers send one).
5. **Vite dev server restart required** after Change 1 — `vite.config.ts` changes are not hot-reloaded.

## Verification

1. **Restart Vite dev server** (vite.config.ts changes require restart):
   ```
   cd web && npm run dev
   ```
2. **Start backend** on `:8000` (if not already running).
3. **Log in** via the frontend UI to populate `localStorage.auth_token`.
4. **Open browser DevTools → Network → WS filter.** Refresh the page.
5. **Verify `/ws/notification` connects:**
   - Request URL should be `ws://localhost:3000/ws/notification?token=<jwt>` (token present).
   - Response status should be `101 Switching Protocols` (successful WS upgrade).
   - No console warnings about reconnect attempts.
6. **Verify `/ws/monitor`:** navigate to the Monitor page, start a monitor run → WS connection to `/ws/monitor?token=<jwt>` should succeed with 101.
7. **Verify `/ws/backtest/{task_id}`:** start a backtest → WS connection to `/ws/backtest/<id>?token=<jwt>` should succeed with 101.
8. **Verify token validation path:** temporarily set `localStorage.auth_token` to an invalid string (`localStorage.setItem('auth_token','invalid')`), refresh → WS should close with code `4001` and reason `invalid token` (confirms backend is now receiving and validating the token). Restore the real token afterward.
9. **Verify anonymous fallback still works:** log out (clears `auth_token`), refresh → WS should still connect as anonymous (101) because the backend's `if token:` guard allows missing tokens. This confirms we didn't break the optional-auth contract.
10. **Run frontend typecheck/lint** if configured:
    ```
    cd web && npm run typecheck   # if present
    cd web && npm run lint        # if present
    ```
    (If no such scripts exist in `package.json`, skip — the change is a small, type-safe edit.)

If step 5 still fails after the proxy fix, the next debug step is to check the backend logs for the actual rejection reason (e.g. origin check, path mismatch) — but the proxy scheme fix is the highest-probability root cause and should resolve all `/ws/*` failures.
