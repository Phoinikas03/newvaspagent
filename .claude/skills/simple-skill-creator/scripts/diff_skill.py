#!/usr/bin/env python3
"""
展示新旧 SKILL.md 的逐条变更审阅界面（GitHub PR 风格）。
用户可逐条 Accept / Reject，最终点击"应用"写回文件。

用法:
  后台启动:
    nohup python scripts/diff_skill.py \\
      --old /tmp/SKILL_snapshot.md \\
      --new <skill目录>/SKILL.md \\
      [--trajectory <轨迹文件>] \\
      > /tmp/skill_diff.log 2>&1 &
  读取 URL: grep '^URL=' /tmp/skill_diff.log
  停止服务: kill $(grep '^PID=' /tmp/skill_diff.log | cut -d= -f2)

典型流程:
  1. 快照旧版: cp <skill>/SKILL.md /tmp/SKILL_snapshot.md
  2. Agent 根据轨迹生成新版 SKILL.md
  3. 启动此脚本，用户逐条审阅变更
  4. 点击"应用已接受的变更"写回文件
"""
import argparse
import difflib
import json
import os
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# 运行时由 main() 填充
STATE = {
    "old_path": None,
    "new_path": None,
    "traj_path": None,
    "old_lines": [],
    "new_lines": [],
    "opcodes": [],   # list of (tag, i1, i2, j1, j2)
}


def find_free_port(start=8800):
    for p in range(start, start + 100):
        try:
            with socket.socket() as s:
                s.bind(("", p))
                return p
        except OSError:
            continue
    raise RuntimeError("No free port available")


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def apply_decisions(decisions: dict) -> str:
    """根据用户决策重建文件内容。decisions = {change_idx: True/False}"""
    result = []
    change_idx = 0
    for tag, i1, i2, j1, j2 in STATE["opcodes"]:
        if tag == "equal":
            result.extend(STATE["old_lines"][i1:i2])
        else:
            accepted = decisions.get(str(change_idx), True)
            if accepted:
                result.extend(STATE["new_lines"][j1:j2])
            else:
                result.extend(STATE["old_lines"][i1:i2])
            change_idx += 1
    return "\n".join(result)


def build_diff_segments() -> list:
    """
    将 opcodes 转换为渲染用的 segment 列表。
    每个 segment: {"type": "context"|"change", ...}
    context 段超过 5 行时折叠。
    """
    segments = []
    change_idx = 0
    for tag, i1, i2, j1, j2 in STATE["opcodes"]:
        if tag == "equal":
            lines = STATE["old_lines"][i1:i2]
            if len(lines) > 8:
                segments.append({
                    "type": "context",
                    "lines": lines[:3],
                    "hidden": len(lines) - 6,
                    "tail": lines[-3:],
                })
            else:
                segments.append({"type": "context", "lines": lines, "hidden": 0, "tail": []})
        else:
            segments.append({
                "type": "change",
                "id": change_idx,
                "tag": tag,
                "old_lines": STATE["old_lines"][i1:i2],
                "new_lines": STATE["new_lines"][j1:j2],
            })
            change_idx += 1
    return segments


def render_segments_html(segments: list) -> str:
    total_changes = sum(1 for s in segments if s["type"] == "change")
    parts = []

    # 统计行
    adds = sum(len(s["new_lines"]) for s in segments if s["type"] == "change" and s["tag"] in ("insert", "replace"))
    dels = sum(len(s["old_lines"]) for s in segments if s["type"] == "change" and s["tag"] in ("delete", "replace"))

    parts.append(f'<div class="diff-stats">共 <b>{total_changes}</b> 处变更 '
                 f'<span class="add-stat">+{adds}</span> '
                 f'<span class="del-stat">−{dels}</span></div>')

    for seg in segments:
        if seg["type"] == "context":
            for line in seg["lines"]:
                parts.append(f'<div class="ctx-line">'
                              f'<span class="ln-sign"> </span>'
                              f'<code>{escape(line)}</code></div>')
            if seg["hidden"] > 0:
                parts.append(f'<div class="fold-line">⋯ {seg["hidden"]} 行未变更 ⋯</div>')
                for line in seg["tail"]:
                    parts.append(f'<div class="ctx-line">'
                                  f'<span class="ln-sign"> </span>'
                                  f'<code>{escape(line)}</code></div>')
        else:
            cid = seg["id"]
            tag = seg["tag"]
            tag_label = {"insert": "新增", "delete": "删除", "replace": "修改"}[tag]
            parts.append(f'<div class="change-block" id="change-{cid}" data-id="{cid}">')
            parts.append(f'  <div class="change-header">'
                         f'    <span class="change-label">变更 #{cid + 1} · {tag_label}</span>'
                         f'    <div class="change-btns">'
                         f'      <button class="btn-accept active" id="accept-{cid}" '
                         f'              onclick="decide({cid}, true)">✓ 接受</button>'
                         f'      <button class="btn-reject" id="reject-{cid}" '
                         f'              onclick="decide({cid}, false)">✗ 拒绝</button>'
                         f'    </div>'
                         f'  </div>')
            parts.append(f'  <div class="change-body">')
            for line in seg["old_lines"]:
                parts.append(f'    <div class="del-line">'
                              f'<span class="ln-sign">−</span>'
                              f'<code>{escape(line)}</code></div>')
            for line in seg["new_lines"]:
                parts.append(f'    <div class="add-line">'
                              f'<span class="ln-sign">+</span>'
                              f'<code>{escape(line)}</code></div>')
            parts.append(f'  </div>')
            parts.append(f'</div>')

    return "\n".join(parts)


def build_html() -> str:
    old_content = Path(STATE["old_path"]).read_text("utf-8")
    new_content = Path(STATE["new_path"]).read_text("utf-8")

    import re
    m = re.search(r'^name:\s*["\']?(.+?)["\']?\s*$', new_content, re.MULTILINE)
    skill_name = m.group(1).strip() if m else Path(STATE["new_path"]).parent.name

    segments = build_diff_segments()
    total_changes = sum(1 for s in segments if s["type"] == "change")
    diff_html = render_segments_html(segments)

    traj_html = ""
    if STATE["traj_path"] and Path(STATE["traj_path"]).exists():
        traj_raw = Path(STATE["traj_path"]).read_text("utf-8", errors="replace")
        traj_html = f'<pre class="traj-content">{escape(traj_raw)}</pre>'
        traj_tab = f'<div class="tab" onclick="showTab(\'traj\',this)">📜 执行轨迹</div>'
    else:
        traj_tab = '<div class="tab disabled" title="未提供轨迹文件">📜 执行轨迹</div>'
        traj_html = '<div class="empty">未提供轨迹文件。使用 --trajectory 参数传入。</div>'

    return f"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>变更审阅 · {skill_name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f8fa;color:#24292f;font-size:14px}}
.topbar{{background:#24292f;color:#fff;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;height:46px}}
.topbar-left{{font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px}}
.topbar-right{{display:flex;align-items:center;gap:12px}}
#progress{{font-size:12px;color:#8c959f}}#progress b{{color:#fff}}
#apply-btn{{background:#238636;color:#fff;border:1px solid #2ea043;padding:5px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}}
#apply-btn:hover{{background:#2ea043}}#apply-btn:disabled{{opacity:.4;cursor:default}}
.tabs{{background:#fff;border-bottom:1px solid #d0d7de;padding:0 24px;display:flex}}
.tab{{padding:11px 16px;cursor:pointer;border-bottom:3px solid transparent;color:#57606a;font-size:13px;user-select:none}}
.tab:hover{{color:#24292f}}.tab.active{{color:#24292f;border-bottom-color:#fd8c73;font-weight:600}}
.tab.disabled{{color:#ccc;cursor:default}}
.wrap{{max-width:1024px;margin:24px auto;padding:0 24px}}
.panel{{display:none}}.panel.active{{display:block}}
/* Diff styles */
.diff-stats{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px 6px 0 0;padding:9px 14px;font-size:13px;color:#57606a;border-bottom:none}}
.add-stat{{color:#1a7f37;font-weight:700}}.del-stat{{color:#cf222e;font-weight:700}}
.diff-body{{background:#fff;border:1px solid #d0d7de;border-radius:0 0 6px 6px;overflow:hidden;margin-bottom:24px}}
.ctx-line,.add-line,.del-line{{display:flex;align-items:baseline;padding:1px 14px;font-family:"SFMono-Regular",Consolas,monospace;font-size:13px;line-height:1.6}}
.ln-sign{{width:18px;min-width:18px;text-align:center;user-select:none;font-weight:700}}
.ctx-line{{background:#fff;color:#57606a}}.ctx-line .ln-sign{{color:#d0d7de}}
.add-line{{background:#e6ffec}}.add-line .ln-sign{{color:#1a7f37}}
.del-line{{background:#ffebe9}}.del-line .ln-sign{{color:#cf222e}}
.fold-line{{background:#f6f8fa;text-align:center;padding:5px;font-size:12px;color:#8c959f;border-top:1px solid #eaecef;border-bottom:1px solid #eaecef}}
/* Change block */
.change-block{{border:1px solid #d0d7de;border-radius:6px;margin-bottom:16px;overflow:hidden;transition:box-shadow .2s}}
.change-block.accepted{{border-color:#2ea043;box-shadow:0 0 0 3px #cdffd8}}
.change-block.rejected{{border-color:#cf222e;box-shadow:0 0 0 3px #ffd7d5;opacity:.7}}
.change-header{{background:#f6f8fa;border-bottom:1px solid #d0d7de;padding:8px 14px;display:flex;align-items:center;justify-content:space-between}}
.change-label{{font-size:12px;font-weight:600;color:#57606a}}
.change-btns{{display:flex;gap:6px}}
.btn-accept,.btn-reject{{border-radius:6px;padding:4px 12px;font-size:12px;font-weight:500;cursor:pointer;border:1px solid;transition:.15s}}
.btn-accept{{background:#fff;border-color:#d0d7de;color:#24292f}}
.btn-accept.active{{background:#2ea043;border-color:#2ea043;color:#fff}}
.btn-reject{{background:#fff;border-color:#d0d7de;color:#24292f}}
.btn-reject.active{{background:#cf222e;border-color:#cf222e;color:#fff}}
.change-body{{border-top:none}}
/* Trajectory */
.traj-content{{background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:20px;font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;max-height:80vh;overflow-y:auto;line-height:1.6}}
.empty{{padding:48px;text-align:center;color:#57606a;background:#fff;border:1px solid #d0d7de;border-radius:6px;line-height:2}}
/* Result toast */
#toast{{display:none;position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#24292f;color:#fff;padding:10px 24px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.3)}}
</style></head><body>
<div class="topbar">
  <div class="topbar-left">🔀 变更审阅 · {skill_name}</div>
  <div class="topbar-right">
    <span id="progress">已审阅 <b>0</b> / {total_changes}</span>
    <button id="apply-btn" onclick="applyChanges()">应用已接受的变更</button>
  </div>
</div>
<div class="tabs">
  <div class="tab active" onclick="showTab('diff',this)">📝 变更审阅</div>
  {traj_tab}
</div>
<div class="wrap">
  <div id="diff" class="panel active">
    <div class="diff-stats-wrap">
{diff_html}
    </div>
  </div>
  <div id="traj" class="panel">
    {traj_html}
  </div>
</div>
<div id="toast"></div>
<script>
const total = {total_changes};
// decisions: {{id: true=accept, false=reject}}，默认全部接受
const decisions = {{}};
for (let i = 0; i < total; i++) decisions[i] = true;
// 初始化所有 change-block 为 accepted 状态
document.querySelectorAll('.change-block').forEach(b => b.classList.add('accepted'));
updateProgress();

function decide(id, accept) {{
  decisions[id] = accept;
  const block = document.getElementById('change-' + id);
  block.classList.toggle('accepted', accept);
  block.classList.toggle('rejected', !accept);
  document.getElementById('accept-' + id).classList.toggle('active', accept);
  document.getElementById('reject-' + id).classList.toggle('active', !accept);
  updateProgress();
}}

function updateProgress() {{
  const reviewed = Object.keys(decisions).length;
  document.querySelector('#progress b').textContent = reviewed;
}}

function showTab(id, el) {{
  if (el.classList.contains('disabled')) return;
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}}

function applyChanges() {{
  const btn = document.getElementById('apply-btn');
  btn.disabled = true;
  btn.textContent = '应用中…';
  fetch('/apply', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{decisions}})
  }}).then(r=>r.json()).then(d=>{{
    if (d.ok) {{
      showToast('✓ 已写入 ' + d.path + '，共应用 ' + d.accepted + ' 处变更，拒绝 ' + d.rejected + ' 处');
      btn.textContent = '已应用';
    }} else {{
      showToast('错误：' + d.error);
      btn.disabled = false;
      btn.textContent = '应用已接受的变更';
    }}
  }}).catch(e=>{{
    showToast('网络错误：' + e);
    btn.disabled = false;
    btn.textContent = '应用已接受的变更';
  }});
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(()=>t.style.display='none', 5000);
}}
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    _html_cache = None

    def do_GET(self):
        if self.path in ("/", ""):
            if Handler._html_cache is None:
                Handler._html_cache = build_html().encode("utf-8")
            self._respond(200, "text/html;charset=utf-8", Handler._html_cache)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/apply":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            decisions = body.get("decisions", {})

            new_content = apply_decisions(decisions)
            target = Path(STATE["new_path"])
            target.write_text(new_content, "utf-8")

            accepted = sum(1 for v in decisions.values() if v)
            rejected = sum(1 for v in decisions.values() if not v)
            result = json.dumps({
                "ok": True,
                "path": str(target),
                "accepted": accepted,
                "rejected": rejected,
            }).encode("utf-8")
            self._respond(200, "application/json", result)
        else:
            self.send_error(404)

    def _respond(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description="SKILL 变更逐条审阅器")
    ap.add_argument("--old", required=True, help="旧版 SKILL.md 路径")
    ap.add_argument("--new", required=True, help="新版 SKILL.md 路径（应用后将覆写此文件）")
    ap.add_argument("--trajectory", default=None, help="执行轨迹文件路径（可选）")
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args()

    old_path = Path(args.old).resolve()
    new_path = Path(args.new).resolve()
    for p, label in [(old_path, "--old"), (new_path, "--new")]:
        if not p.exists():
            print(f"ERROR: {label} file not found: {p}", flush=True)
            raise SystemExit(1)

    old_lines = old_path.read_text("utf-8").splitlines()
    new_lines = new_path.read_text("utf-8").splitlines()
    opcodes = list(difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes())

    STATE.update({
        "old_path": str(old_path),
        "new_path": str(new_path),
        "traj_path": args.trajectory,
        "old_lines": old_lines,
        "new_lines": new_lines,
        "opcodes": opcodes,
    })

    port = args.port or find_free_port()
    print(f"URL=http://localhost:{port}", flush=True)
    print(f"PID={os.getpid()}", flush=True)

    change_count = sum(1 for tag, *_ in opcodes if tag != "equal")
    print(f"Diff viewer: {change_count} changes, serving on port {port} ...", flush=True)

    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
