# newvaspagent

基于 Claude Agent SDK 的 VASP 相关材料与计算助手，支持终端（CLI）与网页（Web）对话。

## 环境要求

- **Python 3.10 及以上**（与 `requirements.txt` 注释一致）
- **推荐使用 Conda**（Miniconda / Anaconda / Mambaforge 等）管理独立环境，便于与系统 Python 及其它项目隔离

## 安装 pip 依赖

在克隆后的仓库根目录执行（示例环境名为 `newvaspagent`，可按需修改）：

```bash
cd /path/to/newvaspagent
conda create -n newvaspagent python=3.10 -y
conda activate newvaspagent
pip install -U pip
pip install -r requirements.txt
```


## 配置环境变量（`.env`）

1. 复制示例文件并编辑：

   ```bash
   cp .env.example .env
   ```

2. 用文本编辑器打开 `.env`，将占位符改为你的真实配置。`.env.example` 中与 Agent / 工具相关的项含义如下：

   | 变量 | 说明 |
   |------|------|
   | `MP_API` | Materials Project API Key（`mp-api`） |
   | `SERPER_API_KEY` | Serper 网页搜索 API（若启用对应搜索工具，不填会回退到DuckDuckGo搜索） |
   | `PMG_VASP_PSP_DIR` | VASP POTCAR 所在目录（pymatgen 生成输入等） |
   | `UPSTREAM_MODEL` | 上游大模型标识（如经 LiteLLM 使用的 `provider/model`） |
   | `UPSTREAM_API_BASE` | 上游 API 根地址，例如`https://host/v1` |
   | `UPSTREAM_API_KEY` | 上游 API Key |

3. 保存 `.env` 后，**无需**提交到 Git（仓库已忽略 `.env`）；团队共享请只提交 `.env.example`。

## 启动 Web 界面

在**仓库根目录**、已 `conda activate` 到上述环境并安装好依赖的前提下：

```bash
python main.py --mode web
```

启动成功后，终端会打印类似：

```text
网页界面: http://localhost:8888
工作目录: .../runs/<时间戳或指定目录>
```

常用可选参数：

- `--port N`：指定端口（默认 **8888**）
- `--dir NAME`：使用 `runs/NAME` 作为工作区并尝试从该目录的 `log.txt` 恢复会话；不传则每次新建带时间戳的子目录

示例：

```bash
python main.py --mode web --port 9000
python main.py --mode web --dir my_run_20260418
```

## 在网页上对话

1. 用浏览器打开终端里提示的地址，一般为 **http://localhost:8888**（若改了 `--port` 则换成对应端口）。
2. 页面加载后，底部有输入框与 **「发送」** 按钮。
3. 在输入框中输入你的问题或任务说明：
   - **Enter**：发送
   - **Shift + Enter**：换行（不发送）
4. 也可点击 **「发送」** 提交。上方区域会依次显示用户消息、助手回复以及工具调用等过程；状态栏会反映是否在处理中。

若页面无法打开，请确认本机防火墙未拦截该端口，且启动命令未报错（例如上游 API、LiteLLM 未就绪等）。

## 命令行模式（可选）

默认模式为终端交互：

```bash
python main.py
# 等价于
python main.py --mode cli
```

更多参数说明可执行：

```bash
python main.py --help
```
