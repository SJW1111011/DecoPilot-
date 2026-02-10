# DecoPilot Docker 部署指南

## 快速开始

### 1. 环境准备

确保已安装：
- Docker 20.10+
- Docker Compose 2.0+

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.template .env

# 编辑 .env 文件，填入 DashScope API Key
# DASHSCOPE_API_KEY=your_api_key_here
```

### 3. 启动服务

```bash
# 仅启动后端 API
docker-compose up -d

# 启动后端 + 前端
docker-compose --profile with-frontend up -d

# 启动完整服务栈（含 Redis）
docker-compose --profile with-frontend --profile with-redis up -d
```

### 4. 验证部署

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f decopilot

# 健康检查
curl http://localhost:8000/health
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API | 8000 | 后端 API 服务 |
| Frontend | 3000 | 前端 Web 服务 |
| Redis | 6379 | 缓存服务（可选） |

## 常用命令

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker-compose exec decopilot bash

# 重新构建镜像
docker-compose build --no-cache

# 清理未使用的资源
docker system prune -f
```

## 数据持久化

以下数据会持久化存储：

- `decopilot-data`: 记忆系统数据库
- `decopilot-logs`: 应用日志
- `./chroma_db`: 向量数据库（知识库）
- `redis-data`: Redis 缓存数据

## 生产环境配置

### 1. 修改环境变量

```bash
# .env
ENV=production
DEBUG=false
CORS_ORIGINS=https://your-domain.com
TRUSTED_HOSTS=your-domain.com
```

### 2. 使用 HTTPS

建议在生产环境使用反向代理（如 Nginx）配置 HTTPS：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 资源限制

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  decopilot:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## 故障排查

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs decopilot

# 检查端口占用
netstat -tlnp | grep 8000
```

### API Key 错误

确保 `.env` 文件中的 `DASHSCOPE_API_KEY` 正确设置。

### 知识库为空

```bash
# 进入容器执行数据导入
docker-compose exec decopilot python -m backend.scripts.ingest_all
```

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```
