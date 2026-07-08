# API 接口文档
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


Base URL: `http://127.0.0.1:8000`

## 通用说明

### 请求格式
- `Content-Type: application/json`
- 字符集 UTF-8

### 响应格式
- 成功：HTTP 2xx + JSON body
- 失败：HTTP 4xx/5xx + `{"detail": "错误信息"}`

### 错误码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功（GET/PUT） |
| 201 | 创建成功（POST） |
| 204 | 无内容（DELETE 成功） |
| 404 | 资源不存在 |
| 409 | 资源冲突（如用户名重复） |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |

---

## 健康检查

### GET `/`
简单探活，不查数据库。

**响应**：
```json
{"status": "ok"}
```

### GET `/health`
完整健康检查，含数据库连通性。

**响应（成功）**：
```json
{"status": "ok", "db": "ok"}
```

**响应（数据库异常）** 503：
```json
{"status": "degraded", "db": "error", "detail": "..."}
```

---

## 用户管理

### GET `/users`
分页获取用户列表。

**查询参数**：

| 参数 | 类型 | 默认 | 约束 | 说明 |
|------|------|------|------|------|
| skip | int | 0 | ≥ 0 | 跳过条数 |
| limit | int | 20 | 1-100 | 每页数量 |

**响应**：
```json
{
  "items": [
    {"id": 1, "username": "alice"},
    {"id": 2, "username": "bob"}
  ],
  "total": 5,
  "skip": 0,
  "limit": 20,
  "has_more": false
}
```

**示例**：
```bash
curl 'http://127.0.0.1:8000/users?skip=0&limit=10'
```

---

### GET `/users/{user_id}`
获取单个用户。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | int | 用户 ID |

**响应** 200：
```json
{"id": 1, "username": "alice"}
```

**响应** 404：
```json
{"detail": "用户 id=999 不存在"}
```

**示例**：
```bash
curl http://127.0.0.1:8000/users/1
```

---

### POST `/users`
创建用户。

**请求体**：
```json
{
  "username": "alice",
  "password": "secret123"
}
```

**字段约束**：

| 字段 | 类型 | 约束 |
|------|------|------|
| username | string | 3-20 位，仅字母数字下划线 |
| password | string | 6-64 位 |

**响应** 201：
```json
{"id": 1, "username": "alice"}
```

**响应** 409：
```json
{"detail": "用户名 'alice' 已存在"}
```

**响应** 422（校验失败）：
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 6 characters"
    }
  ]
}
```

**示例**：
```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'
```

---

### PUT `/users/{user_id}`
更新用户信息，仅更新传入的字段。

**请求体**（所有字段可选）：
```json
{
  "username": "alice_new",
  "password": "newpass456"
}
```

**响应** 200：
```json
{"id": 1, "username": "alice_new"}
```

**响应** 404：用户不存在
**响应** 409：用户名冲突
**响应** 422：校验失败

**示例**：
```bash
curl -X PUT http://127.0.0.1:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"username":"alice_new"}'
```

---

### DELETE `/users/{user_id}`
删除用户。

**响应** 204：无 body
**响应** 404：用户不存在

**示例**：
```bash
curl -X DELETE http://127.0.0.1:8000/users/1
```

---

## Swagger / ReDoc

启动服务后访问：

- **Swagger UI**：http://127.0.0.1:8000/docs
- **ReDoc**：http://127.0.0.1:8000/redoc

支持在线测试所有接口。
