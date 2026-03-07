"""Web UI server for VASP Agent.

Exposes a single WebUI class that:
  - Serves the chat page at GET /
  - Handles WebSocket connections at GET /ws
  - Provides an asyncio Queue for inbound user messages
  - Provides a send() coroutine to push messages to the browser
"""

import asyncio
import json
from aiohttp import web
import aiohttp

WEB_PORT = 8888

# ---------------------------------------------------------------------------
# HTML / CSS / JS
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VASP Agent</title>
<link rel="stylesheet"
  href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.0/marked.min.js"></script>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --user-bg: #1f3557; --agent-bg: #161b22;
    --tool-bg: #1a1f2b; --tool-border: #388bfd;
    --success: #3fb950; --error: #f85149;
    --radius: 10px; --font: 'Segoe UI', system-ui, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    background: var(--bg); color: var(--text);
    font-family: var(--font); font-size: 15px;
    display: flex; flex-direction: column;
  }
  #header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 12px 20px; display: flex; align-items: center; gap: 12px;
    flex-shrink: 0;
  }
  #header h1 { font-size: 17px; font-weight: 600; }
  #status-badge {
    font-size: 12px; padding: 3px 10px; border-radius: 20px;
    background: #21262d; color: var(--muted); border: 1px solid var(--border);
    transition: all .3s;
  }
  #status-badge.thinking {
    background: #1a2a4a; color: var(--accent); border-color: var(--accent);
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  #log-path { margin-left: auto; font-size: 11px; color: var(--muted); }

  #chat-container {
    flex: 1; overflow-y: auto; padding: 20px;
    display: flex; flex-direction: column; gap: 16px;
  }
  #chat-container::-webkit-scrollbar { width: 6px; }
  #chat-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .msg { display: flex; gap: 10px; max-width: 860px; width: 100%; }
  .msg.user { margin-left: auto; flex-direction: row-reverse; }
  .msg-label {
    font-size: 11px; font-weight: 600; color: var(--muted);
    flex-shrink: 0; padding-top: 6px; min-width: 42px; text-align: center;
  }
  .msg-bubble {
    padding: 12px 16px; border-radius: var(--radius);
    line-height: 1.65; border: 1px solid var(--border);
    max-width: calc(100% - 60px);
  }
  .msg.user .msg-bubble { background: var(--user-bg); border-color: #2563a0; white-space: pre-wrap; }
  .msg.agent .msg-bubble { background: var(--agent-bg); }

  .md-content h1,.md-content h2,.md-content h3 { margin: .8em 0 .4em; font-weight: 600; }
  .md-content h1 { font-size: 1.3em; border-bottom: 1px solid var(--border); padding-bottom: .3em; }
  .md-content h2 { font-size: 1.15em; }
  .md-content h3 { font-size: 1.05em; }
  .md-content p { margin: .5em 0; }
  .md-content ul,.md-content ol { margin: .5em 0 .5em 1.4em; }
  .md-content li { margin: .2em 0; }
  .md-content code:not(pre code) {
    font-family: 'Consolas','JetBrains Mono',monospace; font-size: .88em;
    background: #2d333b; padding: 2px 6px; border-radius: 4px; color: #e3b341;
  }
  .md-content pre {
    margin: .7em 0; border-radius: 8px; overflow: hidden;
    border: 1px solid var(--border); font-size: 13px;
  }
  .md-content pre code { padding: 14px 16px; display: block; overflow-x: auto; }
  .md-content blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--muted); margin: .5em 0; }
  .md-content table { border-collapse: collapse; width: 100%; margin: .5em 0; font-size: .93em; }
  .md-content th,.md-content td { border: 1px solid var(--border); padding: 6px 12px; text-align: left; }
  .md-content th { background: #21262d; }
  .md-content a { color: var(--accent); }
  .md-content hr { border-color: var(--border); margin: .8em 0; }
  .md-content strong { color: #f0f6fc; }

  .tool-card {
    background: var(--tool-bg); border: 1px solid var(--tool-border);
    border-radius: var(--radius); overflow: hidden; margin: 12px 0;
  }
  .tool-header {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 14px; cursor: pointer; user-select: none;
    font-size: 13px; color: var(--accent);
  }
  .tool-header:hover { background: #1f2d42; }
  .tool-name { font-weight: 600; font-family: monospace; }
  .tool-toggle { margin-left: auto; font-size: 11px; color: var(--muted); }
  .tool-body {
    display: none; padding: 10px 14px;
    font-family: 'Consolas','JetBrains Mono',monospace;
    font-size: 12px; color: var(--muted); border-top: 1px solid var(--border);
    white-space: pre-wrap; word-break: break-all;
  }
  .tool-body.open { display: block; }

  .result-bar {
    text-align: center; font-size: 12px; color: var(--muted);
    padding: 6px; border-top: 1px solid var(--border); margin-top: 6px;
  }
  .result-bar.ok { color: var(--success); }
  .result-bar.err { color: var(--error); }

  #input-area {
    flex-shrink: 0; background: var(--surface); border-top: 1px solid var(--border);
    padding: 14px 20px; display: flex; gap: 10px; align-items: flex-end;
  }
  #input {
    flex: 1; background: #0d1117; color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 10px 14px; font-family: var(--font); font-size: 14px;
    resize: none; outline: none; min-height: 44px; max-height: 200px;
    line-height: 1.5; overflow-y: auto;
  }
  #input:focus { border-color: var(--accent); }
  #send-btn {
    background: var(--accent); color: #fff; border: none;
    border-radius: var(--radius); padding: 10px 20px;
    font-size: 14px; font-weight: 600; cursor: pointer; height: 44px; flex-shrink: 0;
  }
  #send-btn:hover { background: #79c0ff; }
  #send-btn:disabled { background: #21262d; color: var(--muted); cursor: not-allowed; }
</style>
</head>
<body>
<div id="header">
  <h1>⚛ VASP Agent</h1>
  <span id="status-badge">就绪</span>
  <span id="log-path"></span>
</div>
<div id="chat-container"></div>
<div id="input-area">
  <textarea id="input" rows="1" placeholder="输入问题，Enter 发送，Shift+Enter 换行"></textarea>
  <button id="send-btn">发送</button>
</div>
<script>
marked.setOptions({ breaks: true, gfm: true });

const chat = document.getElementById('chat-container');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const statusBadge = document.getElementById('status-badge');
const logPathEl = document.getElementById('log-path');

let curBubble = null, curMd = null, pendingText = '';

const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onopen  = () => setStatus('已连接', false);
ws.onclose = () => setStatus('连接断开', false);
ws.onerror = () => setStatus('连接错误', false);
ws.onmessage = (ev) => {
  const d = JSON.parse(ev.data);
  if (d.type === 'history') {
    d.events.forEach(e => dispatch(e, true));
    setStatus('就绪', false);
    sendBtn.disabled = false;
    return;
  }
  dispatch(d, false);
};

function dispatch(d, replay) {
  if      (d.type === 'user_message') appendUserMsg(d.text);
  else if (d.type === 'agent_text')   appendText(d.text);
  else if (d.type === 'tool_use')     appendTool(d.name, d.input_str || '');
  else if (d.type === 'result')       appendResult(d);
  else if (d.type === 'log_path')     logPathEl.textContent = d.path;
  else if (!replay && d.type === 'status') setStatus(d.text, d.thinking ?? false);
  else if (!replay && d.type === 'done')   sendBtn.disabled = false;
}

function setStatus(text, thinking) {
  statusBadge.textContent = text;
  statusBadge.className = thinking ? 'thinking' : '';
}
function scrollBottom() { chat.scrollTop = chat.scrollHeight; }

function ensureAgentBubble() {
  if (curBubble) return;
  const row = document.createElement('div');
  row.className = 'msg agent';
  row.innerHTML = '<div class="msg-label">Agent</div>';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  curMd = document.createElement('div');
  curMd.className = 'md-content';
  bubble.appendChild(curMd);
  row.appendChild(bubble);
  chat.appendChild(row);
  curBubble = bubble;
  pendingText = '';
}

function appendText(text) {
  ensureAgentBubble();
  pendingText += text;
  curMd.innerHTML = marked.parse(pendingText);
  curMd.querySelectorAll('pre code').forEach(hljs.highlightElement);
  scrollBottom();
}

function appendTool(name, inputStr) {
  ensureAgentBubble();
  const id = 'tool-' + Math.random().toString(36).slice(2);
  const card = document.createElement('div');
  card.className = 'tool-card';
  card.innerHTML = `
    <div class="tool-header" onclick="toggleTool('${id}')">
      <span>🔧</span>
      <span class="tool-name">${esc(name)}</span>
      <span class="tool-toggle" id="${id}-btn">▶ 展开</span>
    </div>
    <pre class="tool-body" id="${id}">${esc(inputStr)}</pre>`;
  curBubble.appendChild(card);
  scrollBottom();
}

function toggleTool(id) {
  const body = document.getElementById(id);
  const btn  = document.getElementById(id + '-btn');
  btn.textContent = body.classList.toggle('open') ? '▼ 收起' : '▶ 展开';
}

function appendResult(d) {
  ensureAgentBubble();
  const bar = document.createElement('div');
  if (d.error) {
    bar.className = 'result-bar err';
    bar.textContent = `✗ 出错  轮次: ${d.turns}`;
  } else {
    bar.className = 'result-bar ok';
    bar.textContent = `✓ 完成  轮次: ${d.turns}`;
  }
  curBubble.appendChild(bar);
  curBubble = curMd = null;
  pendingText = '';
  scrollBottom();
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function appendUserMsg(text) {
  const row = document.createElement('div');
  row.className = 'msg user';
  row.innerHTML = `<div class="msg-label">You</div><div class="msg-bubble">${esc(text)}</div>`;
  chat.appendChild(row);
  scrollBottom();
}

function send() {
  const text = inputEl.value.trim();
  if (!text) return;
  appendUserMsg(text);
  ws.send(JSON.stringify({ type: 'user_message', text }));
  inputEl.value = '';
  inputEl.style.height = '';
  sendBtn.disabled = true;
  setStatus('思考中...', true);
  curBubble = curMd = null;
  pendingText = '';
}

inputEl.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
inputEl.addEventListener('input',   ()  => { inputEl.style.height = ''; inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px'; });
sendBtn.addEventListener('click', send);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# WebUI class
# ---------------------------------------------------------------------------

_HISTORY_TYPES = {"user_message", "agent_text", "tool_use", "result", "log_path"}


class WebUI:
    def __init__(self, port: int = WEB_PORT) -> None:
        self.port = port
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self._ws: web.WebSocketResponse | None = None
        self._runner: web.AppRunner | None = None
        self._history: list[dict] = []

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._html_handler)
        app.router.add_get("/ws", self._ws_handler)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.port).start()

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def send(self, data: dict) -> None:
        if data.get("type") in _HISTORY_TYPES:
            self._history.append(data)
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send_json(data)
            except Exception:
                pass

    async def _html_handler(self, _request: web.Request) -> web.Response:
        return web.Response(text=_HTML, content_type="text/html")

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws = ws
        # Replay history to newly connected client
        if self._history:
            try:
                await ws.send_json({"type": "history", "events": self._history})
            except Exception:
                pass
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "user_message":
                        self._history.append(data)
                        await self.input_queue.put(data["text"])
                except Exception:
                    pass
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                break
        self._ws = None
        return ws
