# LLM Provider

可插拔的外部 LLM API 架构，支持多种 Provider 通过配置切换，业务代码不绑定单一厂商。

## 源码位置

```
src/llm/
├── factory.py    # LLM 实例工厂
└── providers.py  # Provider 类型定义
```

## 支持的 Provider

配置在 `config/llm_providers.yaml`：

| Provider | 类型 | 默认模型 | API Key 环境变量 |
|----------|------|----------|-----------------|
| deepseek | openai_compatible | deepseek-chat | DEEPSEEK_API_KEY |
| openai | openai_compatible | gpt-4o-mini | OPENAI_API_KEY |
| qwen | openai_compatible | qwen-plus | DASHSCOPE_API_KEY |
| ollama | ollama | qwen2.5:7b | — |
| custom | openai_compatible | 自定义 | CUSTOM_API_KEY |

### Provider 类型

| 类型 | 说明 |
|------|------|
| `openai_compatible` | OpenAI 兼容 API（DeepSeek、OpenAI、通义千问等） |
| `ollama` | 本地 Ollama 服务 |

## 配置示例

```yaml
default_provider: deepseek

providers:
  deepseek:
    type: openai_compatible
    base_url: https://api.deepseek.com/v1
    model: deepseek-chat
    api_key_env: DEEPSEEK_API_KEY
    temperature: 0.7
    timeout: 60
    supports_tool_call: true
```

### 配置字段

| 字段 | 说明 |
|------|------|
| `type` | Provider 类型 |
| `base_url` | API 端点 |
| `model` | 模型名称 |
| `api_key_env` | API Key 环境变量名 |
| `temperature` | 生成温度 |
| `timeout` | 请求超时（秒） |
| `supports_tool_call` | 是否支持 Function Calling |

## 工厂方法

`src/llm/factory.py`：

```python
def create_llm(provider_name: str | None = None) -> BaseChatModel:
    """根据配置创建 LLM 实例。"""
```

流程：

1. 读取 `default_provider` 或用户指定的 provider
2. 合并 `data/user_settings.yaml` 中的覆盖（如自定义 base_url、model）
3. 从 keyring 或 secrets.json 获取 API Key
4. 根据 type 实例化 ChatOpenAI 或 ChatOllama

## 用户切换 Provider

Web 设置面板中：

1. 选择 Provider（下拉列表）
2. 输入 API Key
3. 可选覆盖 model、temperature 等
4. 保存到 `data/user_settings.yaml`

切换 Provider 后，新会话立即生效；已有会话的 Checkpoint 不受影响。

## Tool Calling 要求

Agent 依赖 LLM 的 Function Calling 能力。配置中 `supports_tool_call: true` 的 Provider 可用于 Agent 路径。

Ollama 本地模型需支持 tool call 格式（如 qwen2.5 系列）。

## 使用场景

| 场景 | 使用的 LLM |
|------|-----------|
| Agent ReAct 循环 | 主 Provider（需 tool call） |
| 搜索回答生成 | 主 Provider |
| 链接摘要 | 主 Provider |
| 输入意图 LLM 分类 | 主 Provider |
| Skill 脚本（可选 LLM） | 主 Provider |
