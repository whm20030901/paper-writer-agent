# Day10：故障演练说明（模型不可用回退）

## 场景
上游模型服务不可用（超时、5xx、429 频繁限流）。

## 演练步骤
1. 在 `.env` 中设置：
   - `LLM_API_KEY=test-key`
   - `LLM_MODEL=test-model`
   - `LLM_BASE_URL=http://127.0.0.1:9999`（不可达地址）
2. 启动服务并发起生成请求。
3. 观察结果：请求应成功返回，不应整体失败。

## 预期行为
- `LLMClient` 尝试重试（含 backoff/jitter 与 `Retry-After` 处理逻辑）。
- 超过重试后自动回退到本地草稿生成模板。
- API 仍返回可用 `draft/review/run_id`。

## 排查点
- 若请求直接失败：检查 `llm.py` 回退路径是否被异常短路。
- 若延迟过长：检查 `LLM_MAX_RETRIES`、`LLM_RETRY_BACKOFF_S`、`LLM_RETRY_MAX_DELAY_S`。
- 若回退文案缺失：检查 `subagents_writing.py` 的本地生成分支。
