# 天气查询

基于中国天气网的天气预报查询，支持 Agent 工具、意图识别和斜杠命令，前端以 iframe 渲染天气卡片。

## 源码位置

```
src/tools/weather/
├── tools.py      # get_weather_forecast 工具
├── core.py       # 天气数据解析
├── live.py       # 实时抓取
└── render.py     # HTML 渲染模板

src/tools/weather_render.py  # 遗留渲染入口
```

## Agent 工具

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `get_weather_forecast` | 获取指定城市天气预报 | 否 |

## 触发方式

### 1. 自然语言

意图识别规则匹配「查天气」「天气预报」等 → `INTENT_WEATHER`

### 2. 斜杠命令

```
/weather          # 默认城市
/weather 北京      # 指定城市
/weather shanghai 7d  # 指定城市和天数
```

### 3. Agent 工具调用

对话中「上海明天天气怎么样」→ Agent 调用 get_weather_forecast

## 预报范围

| 范围 | 说明 |
|------|------|
| `today` | 今日天气 |
| `7d` | 7 天预报（默认） |
| `15d` | 15 天预报 |

## 配置

`config/weather.yaml`：

```yaml
default_city_code: "101010100"  # 北京
forecast_days: 7
timeout: 10
```

城市代码为中国天气网 cityId，常用城市可在配置中预设。

## 前端渲染

天气结果不以纯文本展示，而是通过 `render.py` 生成 HTML，在前端 iframe 中渲染天气卡片，包含：

- 当前温度与天气状况
- 多日预报列表
- 天气图标

## 使用示例

```
/weather 深圳
```

或对话：「杭州这周天气如何？」
