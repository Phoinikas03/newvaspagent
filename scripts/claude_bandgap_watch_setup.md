# Claude Bandgap Watch Setup

迁移到另一台服务器时，优先只修改：

- `scripts/claude_bandgap_watch.env.sh`

需要按目标机器实际情况调整的通常只有：

- `BG_DATA_ROOT`
- `VASP_AGENT_PYTHON`
- `VASP_AGENT_CONDA_SH`
- `CLAUDE_CLI`
- `CLAUDE_MODEL`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_API_KEY`
- `BG_TMUX_SESSION`
- `BG_WATCH_SUPERVISOR_SESSION`
- `BG_TASK_DIRS`

## 推荐启动方式

先进入仓库根目录：

```bash
cd /path/to/newvaspagent
```

直接启动：

```bash
bash scripts/start_claude_bandgap_watch.sh
```

停止：

```bash
bash scripts/stop_claude_bandgap_watch.sh
```

查看状态：

```bash
bash scripts/status_claude_bandgap_watch.sh
```

## 查看状态

查看 supervisor：

```bash
tmux attach -t "${BG_WATCH_SUPERVISOR_SESSION:-bgclaudewatch}"
```

查看 vaspagent CLI：

```bash
tmux attach -t "${BG_TMUX_SESSION:-bgvasp}"
```

查看日志：

```bash
tail -f runs/claude_bandgap_watch.supervisor.log
tail -f runs/claude_bandgap_watch.log
```

## Claude Code 注意事项

- watcher 通过 `claude --bare -p` 周期性执行单轮监督判断
- `ANTHROPIC_BASE_URL` 应填写协议根地址，例如 `https://api.sfkey.cn`
- 不要把 `ANTHROPIC_BASE_URL` 写成 `https://api.sfkey.cn/v1`，否则 Claude Code 可能拼出错误路径
