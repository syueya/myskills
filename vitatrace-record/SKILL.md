---
name: vitatrace-record
description: 当用户用自然语言要求记录 VitaTrace 健康数据（如“体重110”“血压120/80”）时使用。
---

# VitaTrace 健康记录

把用户的自然语言转换为 VitaTrace 健康记录，并写入 VitaTrace。

## 触发场景

用户表达“记录、记一下、新增、添加、录入、保存”健康数据时使用，例如：
- `体重110`
- `给妈妈记血压120/80`
- `腰围68 臀围88`

## 环境变量

从环境变量读取连接信息：
- `VITA_TRACE_URL`：VitaTrace API 地址。
- `VITA_TRACE_API_TOKEN`：VitaTrace API Token。

如果任一环境变量缺失，停止执行并提示用户配置环境变量。

## 成员规则

1. 如果用户明确提到成员名，使用该成员。
2. 如果没有提到成员名，使用默认成员，即VitaTrace 中 `isDefault: true` 的成员。
3. 如果仍无法确定成员，向用户确认。

## 时间规则

如果用户没有明确指定日期或时间，直接使用当前对话/执行时刻。格式为：

```text
YYYY-MM-DD HH:mm:ss
```

## 指标映射

常用自然语言映射：

| 说法 | 字段 | 单位 |
| --- | --- | --- |
| 体重 | `weight` | 斤 |
| 血压 `120/80` | `systolicPressure` / `diastolicPressure` | mmHg |
| 心率 | `heartRate` | 次/分 |
| 总胆固醇、TC | `totalCholesterol` | mmol/L |
| 甘油三酯、TG | `triglyceride` | mmol/L |
| 高密度、HDL | `hdlCholesterol` | mmol/L |
| 低密度、LDL | `ldlCholesterol` | mmol/L |
| 腰围 | `waist` | cm |
| 臀围 | `hip` | cm |
| 上胸围 | `upperChest` | cm |
| 下胸围 | `lowerChest` | cm |
| 腹围 | `abdomen` | cm |
| 手臂围 | `arm` | cm |
| 小腿围 | `calf` | cm |
| 大腿围 | `thigh` | cm |
| 身高 | `height` | cm |
| 腿长 | `legLength` | cm |
| 脚长 | `footLength` | cm |
| 脚宽 | `footWidth` | cm |
| 手宽 | `handWidth` | cm |

体重默认单位是斤；如果用户明确写 kg/公斤/千克，换算为斤：`斤 = kg * 2`。

## 记录类型

按填写内容设置记录类型：
- 体重：`weight`
- 血压/心率：`vital`
- 血脂：`lipid`
- 围度：`circumference`
- 身高、腿长、脚长、脚宽、手宽：`body_size`
- 跨多个类别：`mixed`

## 执行步骤
1. 解析用户输入，提取成员、指标、数值和备注。
2. 从 `VITA_TRACE_URL` 和 `VITA_TRACE_API_TOKEN` 读取连接信息。
3. 获取成员列表，按成员规则确定 `memberId`。
4. 使用当前时间构造记录。
5. 调用 VitaTrace API 创建健康记录。
6. 成功后只做简洁确认；失败时说明原因和下一步。

## 回复格式

成功后使用带图标的简洁格式，便于快速分辨成员、时间和指标：

```text
✅ 记录成功
👤 成员：夏夏子
📅 时间：2026-05-13 09:30
⚖️ 体重：110 斤
```

多项记录按指标分行展示：

```text
✅ 记录成功
👤 成员：夏夏子
📅 时间：2026-05-13 09:30
🩺 血压：120/80 mmHg
❤️ 心率：72 次/分
```

常用图标：
- 👤 成员
- 📅 时间
- ⚖️ 体重
- 🩺 血压
- ❤️ 心率
- 🧪 血脂
- 📏 围度/体测
- 📝 备注

失败时也使用清晰图标：

```text
⚠️ 记录失败
原因：未找到默认成员
处理：请先在 VitaTrace 设置默认成员，或在消息中指定成员名。
```


## 示例

**输入：** `体重110`  
**行为：** 默认成员，当前时间，记录 `weight=110`。

**输入：** `给夏夏子记体重55kg`  
**行为：** 指定成员夏夏子，换算并记录 `weight=110`。

**输入：** `血压120/80 心率72`  
**行为：** 默认成员，记录血压和心率。


## 需要追问的情况
- 没有识别到任何指标和值。
- 成员无法确定。
- 用户指定的成员不存在。
- 数值为负数或格式明显不可信。
- VitaTrace 连接失败或鉴权失败。
