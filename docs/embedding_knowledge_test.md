# Embedding 知识库测试手册

本文用于验证本地 Case embedding 索引的完整流程：状态过滤、增量索引、语义查询、元数据过滤、重建和删除。

## 1. 自动化回归测试

在项目根目录运行：

```bash
PYTHONPYCACHEPREFIX=/tmp/oncall-cli-pycache \
PYTHONPATH=src \
python3 -m pytest -q -p no:cacheprovider
```

测试覆盖：

- 一个 Case 生成三个 chunk。
- 重复索引返回 `unchanged`。
- 相似查询优先返回相关 Case。
- `region` 过滤不会返回其他地区 Case。
- 未完成 Case 默认不进入索引。
- `rebuild`、`status` 和 `delete` 正常工作。
- Claude Code 项目 Skill 仍通过 Python registry 路由。

## 2. 准备手工测试目录

```bash
mkdir -p /tmp/oncall-embedding-cases
rm -f /tmp/oncall-embedding-test.db
```

### 样例一：SG event 消费延迟

创建 `/tmp/oncall-embedding-cases/sg-event-delay.json`：

```json
{
  "context": {
    "case_id": "sg-event-delay",
    "created_at": "2026-07-12T10:00:00+08:00",
    "raw_input": "SG ClickHouse event 表数据缺失，下游统计明显变少",
    "normalized_symptom": "event data missing",
    "environment": "production",
    "time_range": "最近一小时",
    "entities": {"region": "sg", "system": "clickhouse", "table": "event"},
    "user_supplied": {}
  },
  "report": {
    "case_id": "sg-event-delay",
    "status": "resolved",
    "conclusion": "消费任务积压导致 event 数据延迟落入 ClickHouse",
    "confidence": "confirmed",
    "route": {"candidates": [], "selected_skill_id": "diagnose-ck-not-correct"},
    "skill_id": "diagnose-ck-not-correct",
    "skill_version": "1.0.0",
    "evidence": [{"summary": "consumer lag 持续升高", "source": "clickhouse-readonly"}],
    "missing_information": [],
    "next_steps": ["恢复消费任务", "验证 event 数据追平"]
  }
}
```

### 样例二：EU AB 配置同步失败

创建 `/tmp/oncall-embedding-cases/eu-ab-sync.json`，结构与样例一相同，并替换这些字段：

```json
{
  "context": {
    "case_id": "eu-ab-sync",
    "created_at": "2026-07-12T11:00:00+08:00",
    "raw_input": "EU AB 实验配置与平台配置不一致",
    "normalized_symptom": "ab configuration inconsistent",
    "environment": "production",
    "time_range": "最近两小时",
    "entities": {"region": "eu", "system": "clickhouse", "table": "ab"},
    "user_supplied": {}
  },
  "report": {
    "case_id": "eu-ab-sync",
    "status": "resolved",
    "conclusion": "AB 配置同步任务失败，ClickHouse 中仍是旧版本",
    "confidence": "confirmed",
    "route": {"candidates": [], "selected_skill_id": "diagnose-ck-not-correct"},
    "skill_id": "diagnose-ck-not-correct",
    "skill_version": "1.0.0",
    "evidence": [{"summary": "同步任务失败且版本号落后", "source": "readonly-query"}],
    "missing_information": [],
    "next_steps": ["恢复同步任务", "核对 AB 配置版本"]
  }
}
```

### 样例三：尚未完成的 Case

复制样例一为 `blocked.json`，把 `case_id` 改为 `blocked-case`，并把报告状态和结论改为：

```json
"status": "blocked_by_incomplete_skill",
"conclusion": "尚未执行调查"
```

## 3. 使用离线 provider 测试

### 3.1 重建索引

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  rebuild --cases-root /tmp/oncall-embedding-cases
```

预期：两个 resolved Case 显示 `indexed`，blocked Case 显示 `skipped`。

### 3.2 查看状态

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  status
```

预期：`cases` 为 2，`chunks` 为 6。

### 3.3 查询 SG event 问题

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  search "SG event 数据消费延迟和事件缺失" --limit 2
```

预期：`sg-event-delay` 排在第一位，并返回匹配 chunk、相似度和原始 JSON 路径。

### 3.4 验证地区过滤

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  search "配置同步失败" --region eu
```

预期：只返回 `eu-ab-sync`。

### 3.5 验证增量更新

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  index /tmp/oncall-embedding-cases/sg-event-delay.json
```

未修改文件时预期返回 `unchanged`。修改结论后再次执行，预期返回 `indexed`。

### 3.6 验证删除

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-test.db \
  --provider hashing \
  delete eu-ab-sync
```

预期返回 `deleted`；再次查询 EU 时应返回空数组。

## 4. 使用本地语义模型测试

先启动 Ollama 并准备 embedding 模型，然后执行：

```bash
export ONCALL_EMBEDDING_PROVIDER=ollama
export ONCALL_EMBEDDING_MODEL=nomic-embed-text

PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-ollama.db \
  rebuild --cases-root /tmp/oncall-embedding-cases

PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-embedding-ollama.db \
  search "新加坡事件数据因为消费积压没有及时到达"
```

预期：即使查询没有复用样例中的原词，语义模型仍应优先返回 `sg-event-delay`。不要用 hashing provider 建立索引后再用 Ollama 查询同一个数据库；切换 provider 或模型时应使用新数据库或执行 `rebuild`。

## 5. 验收标准

- 索引操作幂等，Case 内容变更后能够更新。
- 默认不会把未完成 Case 当作已解决知识。
- 语义查询能返回原始 Case，而不只返回生成摘要。
- region/environment/system 过滤有效。
- 搜索结果明确标记 Skill 版本和相似度。
- 切换 embedding provider 后不会混合比较旧向量。
- 删除、重建和状态检查均可独立执行。
