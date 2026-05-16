---
name: openclaw-model-manage
version: 1.0.0
description: 管理 OpenClaw 模型配置，支持添加/删除模型/删除供应商/修改/查询等操作
allowed-tools: Bash(node:*), Bash(mkdir:*)
---

# openclaw-model-manage

## 用户输入

比如：

- "添加 siliconflow 的 DeepSeek-V3 模型"
- "获取 longcat 的模型列表"
- "删除 siliconflow 的 DeepSeek-V3"
- "删除 siliconflow 供应商"
- "移除这个供应商"
- "测试 longcat 的 gpt-4o 能不能用"
- "更新 siliconflow 的 API Key"

**不需要用户构造任何参数**，我来解析你的话，构造参数，执行操作，返回结果。

如果信息不全，我会告诉你还缺什么。

---

## 执行步骤


### 1. 解析意图 → 确定 action

| 你的话（关键词） | action |
|---|---|
| "添加"、"加个模型" | `add` |
| "删除供应商"、"删除这个供应商"、"移除供应商" | `delete_provider` |
| "删除"、"移除" | `delete` |
| "列表"、"有哪些"、"获取模型" | `list` |
| "测试"、"能不能用"、"是否正常" | `test` |
| "更新 key"、"修改密钥" | `update_key` |

### 2. 提取信息 → 构造 PARAMS

我把你说的内容填进这个 JSON：

```json
{
  "action": "add|delete|delete_provider|list|test|update_key",
  "provider": "供应商名称",
  "base_url": "API 地址（新供应商必须）",
  "api_key": "API 密钥（新供应商必须）",
  "model": "模型 ID（add/delete/test 必须）",
  "alias": "别名（可选）",
  "api_type": "openai|anthropic（默认 openai）",
  "skip_validation": false,
  "new_base_url": "新 API 地址（update_key 用）",
  "new_api_key": "新 API 密钥（update_key 用）"
}
```

### 3. 执行脚本

```bash
PARAMS='<构造好的JSON>' python openclaw-model-manage.py
```

---

## 六种操作

### add - 添加模型

- 自动验证 API 和模型有效性
- 写入 `~/.openclaw/openclaw.json`
- 自动备份原配置

**对话示例：**
> 你：添加 siliconflow 的 DeepSeek-V3
> 我：好的，请提供 API 地址和 Key
> 你：地址是 https://api.siliconflow.cn/v1，Key 是 sk-xxx
> 我：（验证通过，添加成功）

### delete - 删除模型

- 从 `models[]` + `fallbacks[]` + `agents.defaults.models[]` 中清理
- 删除默认模型时自动切换到下一个
- 供应商清空时自动删除整条记录

**对话示例：**
> 你：删除 siliconflow 的 DeepSeek-V3
> 我：（直接执行，告诉你删了哪些引用）

### delete_provider - 删除供应商

- 删除该供应商下的所有模型
- 同步清理 `agents.defaults.model.fallbacks`
- 同步清理 `agents.defaults.models[]`
- 如果默认模型属于该供应商，则自动切换到剩余供应商中的第一个可用模型

**对话示例：**
> 你：删除 siliconflow 供应商
> 我：（删除该供应商及其全部模型，并修复默认模型）

### update_key - 修改密钥

- 只改 baseUrl 或 apiKey，不动其他配置

**对话示例：**
> 你：更新 siliconflow 的 API Key
> 我：新的 Key 是多少？
> 你：sk-new-xxx
> 我：（更新成功）

### list - 获取模型列表

- 从 API 查询，只读，不改文件

**对话示例：**
> 你：longcat 有哪些模型
> 我：列出来给你

### test - 测试模型

- 不指定模型 → 自动取列表第一个测试
- 只读操作

**对话示例：**
> 你：测试 longcat 的模型
> 我：（自动获取列表，用第一个测试，报告结果）
> 你：测试 longcat 的 LongCat-Flash-Chat
> 我：（测试指定的模型）

---

## 缺失信息时

输出 `=== MISSING_INFO ===` 块，告诉你缺什么，并列出已有配置供参考。我会继续问你。
