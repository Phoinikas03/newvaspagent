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
   | `LLM_API_BASE` | 上游 API 根地址，例如 `https://host/v1` |
   | `LLM_API_KEY` | 上游 API Key |
   | `LLM_MODEL` | 模型名，写上游认的**裸名**（如 `glm-5`），不要加 `anthropic/` 等 provider 前缀 |

   上游只需这一组。启动时会自动探测它是否支持 Anthropic `/v1/messages`：支持就让
   Claude Agent SDK 直连，不支持则在 agent 进程内拉起一个协议桥
   （`litellm.anthropic_messages()`）做转换，不落配置文件、不起独立服务。
   探测误判时可加 `--force-litellm` 强制走协议桥。

   旧变量名 `UPSTREAM_MODEL` / `UPSTREAM_API_BASE` / `UPSTREAM_API_KEY` 仍作兼容回退，
   新配置请用上表的名字。`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` 由程序自动写入，
   **不需要**你在 `.env` 里设置。

3. 保存 `.env` 后，**无需**提交到 Git（仓库已忽略 `.env`）；团队共享请只提交 `.env.example`。

## 启动 Web 界面

在**仓库根目录**、已 `conda activate` 到上述环境并安装好依赖的前提下：

```bash
python main.py --mode web
```

启动成功后，终端会打印类似：

```text
网页界面: http://localhost:18688
工作目录: .../runs/<时间戳或指定目录>
```

常用可选参数：

- `--port N`：指定端口（默认 **18688**）
- `--dir NAME`：使用 `runs/NAME` 作为工作区并尝试从该目录的 `log.txt` 恢复会话；不传则每次新建带时间戳的子目录

示例：

```bash
python main.py --mode web --port 9000
python main.py --mode web --dir my_run_20260418
```

## 在网页上对话

1. 用浏览器打开终端里提示的地址，一般为 **http://localhost:18688**（若改了 `--port` 则换成对应端口）。
2. 页面加载后，底部有输入框与 **「发送」** 按钮。
3. 在输入框中输入你的问题或任务说明：
   - **Enter**：发送
   - **Shift + Enter**：换行（不发送）
4. 也可点击 **「发送」** 提交。上方区域会依次显示用户消息、助手回复以及工具调用等过程；状态栏会反映是否在处理中。

若页面无法打开，请确认本机防火墙未拦截该端口，且启动命令未报错（例如上游 API 不可达、Key 失效等）。

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
