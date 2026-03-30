# Day5：5 分钟演示脚本（面试版）

## 0:00 - 0:40 项目定位
- 这是一个可部署的 Paper Writer Agent 服务，不只是离线 demo。
- 核心目标：`生成 -> 评审 -> 修订 -> 指标追踪` 全链路闭环。

## 0:40 - 1:30 架构讲解
- API 层：FastAPI 路由按 generation/runs/export/insights/revision 拆分。
- 服务层：`PaperService` 做编排入口与持久化协同。
- 编排层：`PaperPipeline` 负责 writer/reviewer/gate 迭代。
- 子能力层：研究/写作/评审拆分为独立 subagent 模块。

## 1:30 - 2:40 在线生成演示
- 打开首页，输入任务：
  - task: `Agentic workflow for evidence-grounded paper writing`
  - outline: `Introduction, Method, Evaluation, Conclusion`
- 点击 Generate，展示：
  - draft（含 References）
  - review_report（结构/证据/引用/语言 + 质量分）
  - stop_reason（达阈值提前停止或达到最大轮次）

## 2:40 - 3:30 运行追踪与可观测
- 打开 runs 列表，展示筛选/排序。
- 点开 run detail，展示 lineage/source/revision-plan。
- 展示 metrics：总运行数、平均质量分、停止原因分布。

## 3:30 - 4:20 导出与运维能力
- 调用 `GET /v1/papers/runs/export.csv` 演示报表导出。
- 展示 `/health` 与 `/ready` 探针含义。
- 提及 API Key、rate limit、idempotency key 三个保护机制。

## 4:20 - 5:00 收尾（工程亮点）
- Day4 已完成编排与子能力拆分，`agents.py` 不再承担全部实现细节。
- Day5 已补回归测试与演示文档，便于持续迭代和面试讲解。
- 后续可扩展：prompt version 持久化、证据覆盖率指标、前端 diff 可视化。
