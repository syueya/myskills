---
name: mcp-ezbookkeeping
version: 1.0.0
description: 使用 MCP 协议连接 ezBookkeeping 记账服务，根据自然语言描述自动完成记账。触发场景：用户说"中午吃饭花了35块"、"昨天收到工资5000"、"转账给张三200元"等消费/收入/转账描述时，自动解析并调用 MCP 服务完成记账。
---

# MCP ezBookkeeping 智能记账

根据用户的自然语言描述，自动解析交易信息并通过 MCP 协议完成记账。

## 前置要求

配置文件路径：`/root/config/mcporter.json`

**服务器名称**：`mcp-ezbookkeeping`

**工具调用格式**：`mcporter call mcp-ezbookkeeping.tool_name --config /root/config/mcporter.json`

配置文件路径：`/root/config/mcporter.json`

## 触发条件

用户描述消费、收入、转账等财务行为时触发，例如：
- "中午吃饭花了35块"
- "昨天收到工资5000"
- "转账给张三200元"

## 记账流程

### 1. 解析交易信息

| 维度 | 规则 |
|------|------|
| **时间** | 未提及→当前时间；相对时间→解析为具体时间；**统一使用 Asia/Shanghai (UTC+8)**<br>⚠️ **重要**：传入时间需转换为上海时区（如晚上6点记为 `18:00:00+08:00`），格式 `2026-03-21T18:01:00+08:00` |
| **类型** | 花了/买了→expense；收到/工资→income；转账→transfer |
| **金额** | 提取数字，默认 CNY |
| **账户** | 微信→微信钱包；支付宝→支付宝；未指定→第一个账户 |
| **分类** | 餐饮→食品；交通→交通出行；电费→水电煤气；饮料→牛奶饮料；护发素/洗护→化妆护肤；内裤/袜子等贴身衣物→衣服鞋袜；发饰等小饰品且无更贴切类目时→其他支出；空气清新剂、备菜架、收纳架等家居清洁/收纳用品→家居用品 |
| **标签** | 工作/家庭/旅游/礼物等关键词匹配 |

### 2. 查询基础信息

```bash
# 账户列表
mcporter call mcp-ezbookkeeping.query_all_accounts --config /root/config/mcporter.json

# 分类列表
mcporter call mcp-ezbookkeeping.query_all_transaction_categories --config /root/config/mcporter.json

# 标签列表
mcporter call mcp-ezbookkeeping.query_all_transaction_tags --config /root/config/mcporter.json
```

### 3. 执行记账

```bash
mcporter call mcp-ezbookkeeping.add_transaction \
  --config /root/config/mcporter.json \
  --args '{
    "type": "expense",
    "time": "2026-03-21T16:01:00+08:00",
    "category_name": "食品",
    "account_name": "微信钱包",
    "amount": "35",
    "comment": "中午吃饭花了35块",
    "tags": ["工作"]
  }'
```

**参数说明**：
- `type`: expense / income / transfer
- `time`: **上海时区**（UTC+8），格式 `2026-03-21T18:01:00+08:00`
  - ⚠️ 注意：ezBookkeeping 会按传入时间直接显示，需确保传入的是上海时区时间（如晚上6点 = `18:00:00+08:00`）
- `category_name`: 二级分类名称
- `account_name`: 账户名称
- `amount`: 金额（字符串）
- `comment`: 备注（可选）
- `tags`: 标签数组（可选）

## 输出格式

```
✅ 记账成功

💰 金额：¥35.00
📅 时间：2026-03-21 18:01
📂 类型：支出
💳 账户：微信钱包
🏷️ 分类：食品
🔖 标签：工作
📝 备注：中午吃饭花了35块
```

**无标签时不显示标签行**

## 时间处理规则

| 场景 | 处理方式 |
|------|----------|
| 用户未指定时间 | 使用用户发送消息的时间，转换为上海时区（+8小时） |
| 用户指定相对时间（如"昨天"） | 解析为具体日期，时间设为 12:00:00+08:00 |
| 用户指定具体时间（如"晚上6点"） | 转换为 `18:00:00+08:00` |

**关键**：ezBookkeeping 直接显示传入的时间，不会自动转换时区。传入的时间必须是上海时区（UTC+8），否则显示会偏差 8 小时。

## 错误处理

- **失败时明确告知**：记账失败 + 错误原因
- **无法解析金额**：询问具体金额
- **无可用账户**：提示先创建账户
- **账户不存在**：检查名称拼写

## MCP 工具参考

| 工具名 | 用途 |
|--------|------|
| `query_all_accounts` | 获取所有账户 |
| `query_all_accounts_balance` | 获取所有账户余额 |
| `query_all_transaction_categories` | 获取交易分类 |
| `query_all_transaction_tags` | 获取标签 |
| `add_transaction` | 创建交易 |
| `query_transactions` | 查询交易记录 |
| `query_latest_exchange_rates` | 查询汇率 |

## 注意事项

- 必须用 `--args` 传递 JSON 参数
- 时间使用 `+08:00` 时区格式，不是 `Z`
- 金额用字符串类型
- 分类和账户使用**名称**，不是 ID
