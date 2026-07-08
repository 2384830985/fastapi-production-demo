# MySQL 初始化脚本目录

放在这里的 `.sql` / `.sh` 文件会在 MySQL 容器首次启动时自动执行（按文件名字母序）。

## 用法

比如要给应用创建专用账号（而非用 root），创建 `01-create-user.sql`：

```sql
CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'app_password';
GRANT ALL PRIVILEGES ON testdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```

然后修改 `.env`：
```
DB_USER=appuser
DB_PASSWORD=app_password
```

⚠️ 注意：脚本只在数据卷为空时（首次启动）执行。
如果已经启动过，需要 `docker compose down -v` 清掉数据卷才会重新执行。
