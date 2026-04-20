# Codex Bandgap Watch Setup

迁移到另一台服务器时，优先只修改：

- `scripts/codex_bandgap_watch.env.sh`

需要按目标机器实际情况调整的通常只有：

- `BG_DATA_ROOT`
- `VASP_AGENT_PYTHON`
- `VASP_AGENT_CONDA_SH`
- `CODEX_CLI`
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
bash scripts/start_codex_bandgap_watch.sh
```

停止：

```bash
bash scripts/stop_codex_bandgap_watch.sh
```

查看状态：

```bash
bash scripts/status_codex_bandgap_watch.sh
```

## 查看状态

查看 supervisor：

```bash
tmux attach -t "${BG_WATCH_SUPERVISOR_SESSION:-bgwatch}"
```

查看 vaspagent CLI：

```bash
tmux attach -t "${BG_TMUX_SESSION:-bgvasp}"
```

查看日志：

```bash
tail -f runs/codex_bandgap_watch.supervisor.log
tail -f runs/codex_bandgap_watch.log
```
