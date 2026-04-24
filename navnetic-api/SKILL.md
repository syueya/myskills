---
name: navnetic-api
version: 1.0.0
description: 通过当前 Navnetic 后端 HTTP API 搜索网址，并新增、编辑、删除分类和网址。用户要查找网址、添加书签、维护导航数据，或明确提到 Navnetic / 导航站 / 书签管理时优先使用。
---

# Navnetic API

只处理 Navnetic 导航数据：搜索网址，以及新增、编辑、删除分类和网址。

## 固定规则

- 需要配置导航页地址，不配置默认地址是：`${NAVNETIC_BASE_URL:-http://localhost:22680}`。
- 需要鉴权时使用 `Authorization: Bearer ${NAVNETIC_TOKEN}`；不要猜 token 或 ID。
- 编辑前读原数据并保留未提及字段；删除前确认唯一目标。
- 只处理网址搜索，以及分类/网址的新增、编辑、删除。

## 接口速查

### 搜索网址

```bash
curl -sS \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/search?keyword=example"
```

- 方法：`GET`
- 参数：`keyword`，最长 100 字符；为空返回空数组。
- 匹配字段：`name`、`href`、`description`。
- 返回：网址数组，包含 `id`、`name`、`icon`、`href`、`description`，不包含 `category_id`。

### 读取全部数据 / 定位 ID

```bash
curl -sS "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/read"
```

用途：列出分类、确定 `category_id`、定位网址所在分类、编辑前读取原记录。

返回外层是 `{ code, data, msg }`，`data` 是分类数组：

```json
{
  "category_id": 3,
  "category_name": "AI",
  "category_icon": "brain",
  "url": [
    {
      "id": 12,
      "name": "Example",
      "icon": "",
      "href": "https://example.com",
      "description": "示例站点"
    }
  ]
}
```

### 新增分类

不要传 `category_id`。

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"category_name":"AI 工具","category_icon":"brain"}' \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/addCategory"
```

### 编辑分类

必须传已有 `category_id`，并保留未修改字段。

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"category_id":3,"category_name":"AI 工具","category_icon":"brain"}' \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/addCategory"
```

### 删除分类

```bash
curl -sS -X DELETE \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/delCategory?category_id=3"
```

### 新增网址

必须先确定 `category_id`；不要传 `id`。

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Example","icon":"","href":"https://example.com","description":"示例站点"}' \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/addUrl?category_id=3"
```

### 编辑网址

必须传已有 `id`，并通过 `category_id` 指定所在分类。

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"id":12,"name":"Example","icon":"","href":"https://example.com","description":"更新后的描述"}' \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/addUrl?category_id=3"
```

### 删除网址

```bash
curl -sS -X DELETE \
  -H "Authorization: Bearer ${NAVNETIC_TOKEN}" \
  "${NAVNETIC_BASE_URL:-http://localhost:22680}/api/delUrl?category_id=3&url_id=12"
```

## 执行流程

### 搜索网址

1. 调 `/api/search?keyword=...`。
2. 返回命中网址、链接、`url_id`。
3. 只有需要编辑、删除或确认分类时，才调 `/api/read` 定位 `category_id`。

### 新增网址

1. 用 `/api/read` 确认目标分类的 `category_id`。
2. 用 `/api/search` 检查是否已有相同或相近网址。
3. 调 `/api/addUrl?category_id=...`。
4. 告诉用户新增到了哪个分类。

### 编辑网址

1. 用 `/api/search` 找到网址。
2. 用 `/api/read` 定位 `category_id` 并读取原记录。
3. 合并用户要改的字段后调 `/api/addUrl?category_id=...`。
4. 告诉用户更新了哪些字段。

### 删除网址

1. 用 `/api/search` 找到网址。
2. 用 `/api/read` 定位 `category_id`。
3. 明确将删除的网址后再调 `/api/delUrl`。

### 分类操作

- 新增分类：直接调 `/api/addCategory`，必要时先用 `/api/read` 检查是否重名。
- 编辑分类：先用 `/api/read` 确认 `category_id` 和原字段，再调 `/api/addCategory`。
- 删除分类：先用 `/api/read` 确认 `category_id`，提醒会删除分类下所有网址，再调 `/api/delCategory`。

## 错误处理

- `401`：检查 Bearer token 是否缺失或错误。
- `400`：检查方法、必填字段、查询参数和 JSON 字段名。
- 多个候选目标：先让用户选择，不要自行决定。
