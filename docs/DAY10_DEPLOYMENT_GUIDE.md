# Day10：Docker 一键启动演示说明

## 目标
用最少步骤在本地完成「构建 -> 启动 -> 健康检查 -> 页面演示」。

## 1) 准备环境变量
```bash
cp .env.example .env
```

可按需修改：
- `APP_PORT`
- `API_KEY`
- `LLM_API_KEY` / `LLM_MODEL`（不填则走本地回退生成）

## 2) 构建镜像
```bash
docker build -t paper-writer-agent:latest .
```

## 3) 一键启动容器
```bash
docker run --rm \
  --name paper-writer-agent \
  -p 8000:8000 \
  --env-file .env \
  paper-writer-agent:latest
```

## 4) 验证服务
```bash
curl -s http://127.0.0.1:8000/health
curl -s -i http://127.0.0.1:8000/ready
```

访问：
- UI: `http://127.0.0.1:8000/`
- OpenAPI: `http://127.0.0.1:8000/docs`

## 5) 演示主链路
1. 在 UI 输入 task/outline，点击 Generate。
2. 查看 run detail、lineage、metrics。
3. 导出 CSV：`/v1/papers/runs/export.csv`。

## 6) 停止服务
```bash
docker stop paper-writer-agent
```
