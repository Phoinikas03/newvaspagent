# newvaspagent 框架整理

本文基于当前仓库代码整理 `newvaspagent` 的整体框架与一次完整交互的执行链路，并配套两张 SVG 图：

- [framework-overview.svg](./framework-overview.svg): 模块框架图
- [interaction-flow.svg](./interaction-flow.svg): 交互流程图

## 1. 总体定位

`newvaspagent` 是一个围绕 `claude_agent_sdk` 组装的 VASP 任务代理，提供两种入口：

- CLI 模式：终端对话
- Web 模式：网页对话 + 历史回放 + Todo 面板

它本身不直接实现大模型，而是通过 `src/litellm_proxy.py` 把 SDK 请求转发到 LiteLLM 或兼容的上游模型服务。

## 2. 代码分层

### 入口层

- `main.py`
  - 仓库根入口，负责把执行转交给 `src.main.main()`
- `src/main.py`
  - 参数解析
  - 工作目录解析
  - LiteLLM 环境配置与自启动
  - Claude SDK 选项构建
  - CLI / Web 主循环

### Agent 运行层

- `build_options()`
  - 组装 `ClaudeAgentOptions`
  - 注入系统提示词
  - 注册 MCP tools
  - 限制可调用工具白名单
- `ClaudeSDKClient`
  - 负责 `query()` 发起用户请求
  - 负责 `receive_messages()` 持续接收消息流

### 工具层

- `src/tool_wrapper.py`
  - 把底层实现封装成 SDK 可注册的 tool
- `src/tool.py`
  - 真正的工具逻辑实现，包括：
  - VASP 输入文件生成
  - DuckDuckGo / Google 搜索
  - 网页抓取
  - arXiv / Semantic Scholar 学术检索
- `.claude/skills/structure`
  - 负责 Materials Project 结构抓取、ASE/pymatgen 结构构建、slab/吸附结构枚举与校验

### 状态与恢复层

- `src/conversation_store.py`
  - 将用户/助手文本写入 `conversation_turns.jsonl`
  - 在无法 resume 时，把历史注入到 system prompt
- `webui/web_history.py`
  - 记录用户输入到 `log.txt`
  - 把 SDK 消息重放为 Web 前端事件
  - 处理 TodoWrite 的 UI 映射
- `src/result_message.py`
  - 补充判断 ResultMessage 是否失败

### 展示层

- `webui/web.py`
  - 提供 HTTP 页面、WebSocket、输入队列、事件推送
- `src/main.py` 中的 `_dispatch_message_to_cli()` / `_dispatch_message_to_web()`
  - 将 SDK 消息分发到终端或网页

## 3. 启动链路

程序启动后的主路径如下：

1. `main.py` 进入 `src.main.main()`
2. 解析参数 `--mode / --dir / --port / --base-url`
3. 调用 `configure_anthropic_for_litellm()`
4. 视情况调用 `maybe_start_litellm()`
5. 调用 `resolve_workspace()` 解析工作目录与恢复 session
6. 若不能 resume，则尝试从 `conversation_turns.jsonl` 注入持久化上下文
7. 进入 `cli_main()` 或 `web_main()`
8. 创建 `ClaudeSDKClient`，启动消息接收循环

## 4. 一次交互的核心机制

无论是 CLI 还是 Web，本质上都遵循同一个模式：

1. 用户输入进入本地输入队列
2. 用户原文先写入 `log.txt`
3. 再调用 `client.query(user_input)`
4. 后台 `receive_messages()` 持续收到：
   - `AssistantMessage`
   - `UserMessage`（通常承接工具结果）
   - `SystemMessage`
   - `ResultMessage`
5. 分发器把这些消息：
   - 追加写入 `log.txt`
   - 同步写入持久化上下文
   - 推送到 CLI 或 Web UI
6. 若触发工具调用，则通过 MCP server 执行 `src/tool_wrapper.py` 中注册的工具
7. 工具结果再次回到消息流
8. 最后由 `ResultMessage` 标记当前回合完成或失败

## 5. Web 模式的额外能力

相对 CLI，Web 多了三层能力：

- 页面服务：`WebUI.start()` 启动 HTTP + WebSocket
- 历史回放：`parse_log_file_to_ui_events()` 在页面打开时重建旧记录
- Todo 面板：把 `TodoWrite` 的内容实时投影到右侧任务栏

## 6. 当前架构特点

优点：

- CLI 与 Web 共用同一套 Agent 核心，避免双份逻辑分叉
- 工具层与界面层分离较明确
- `log.txt` + `conversation_turns.jsonl` 同时覆盖了回放与上下文续接两类需求
- LiteLLM 自启动逻辑独立，便于切换本地代理与远程兼容服务

需要注意的点：

- `src/main.py` 体量较大，启动、调度、CLI、Web 分发都堆在一个文件中
- Web/CLI 的消息分发逻辑相似度较高，后续可以继续抽象复用
- `tool_wrapper.py` 和 `tool.py` 的职责是清晰的，但工具数量继续增长时可以再按领域拆分模块
