# Case 与知识库数据结构

本文说明一个 Oncall Case 如何从原始 JSON 转换为本地 embedding 知识库记录，以及查询结果如何回到原始证据。

## 1. 数据存放位置

原始 Case 保存在：

```text
cases/<case-id>.json
```

embedding 知识库默认保存在：

```text
knowledge/knowledge.db
```

`knowledge.db` 是本地 SQLite 数据库，用于保存检索元数据、可读文本片段和 embedding 向量。原始 Case JSON 是事实源，知识库通过 `source_path` 指回原始文件。`cases/` 和 `knowledge/` 默认都不提交 Git。

## 2. 原始 Case JSON

一个 Case 由 `context` 和 `report` 两部分组成。

### 2.1 Context

`context` 保存用户输入和调查上下文：

| 字段 | 作用 | 示例 |
| --- | --- | --- |
| `case_id` | Case 唯一标识 | `sg-event-delay` |
| `created_at` | 创建时间 | `2026-07-12T10:00:00+08:00` |
| `raw_input` | 用户原始描述 | `SG ClickHouse event 表数据缺失` |
| `normalized_symptom` | 规范化后的现象 | `event data missing` |
| `environment` | 环境 | `production` |
| `time_range` | 调查时间范围 | `最近一小时` |
| `entities` | 地区、系统、表等实体 | `region=sg, table=event` |
| `user_supplied` | 调查中由用户补充的信息 | 数据库名、表名等 |

### 2.2 Report

`report` 保存路由和调查结果：

| 字段 | 作用 | 示例 |
| --- | --- | --- |
| `status` | 调查状态 | `resolved` |
| `conclusion` | 调查结论 | `消费积压导致数据延迟` |
| `confidence` | 结论置信状态 | `confirmed` |
| `route` | 路由候选、选择和原因 | 选择 CK 数据排查 Skill |
| `skill_id` | 使用的 Skill | `diagnose-ck-not-correct` |
| `skill_version` | Skill 版本 | `1.0.0` |
| `evidence` | 支撑结论的证据 | consumer lag 升高 |
| `missing_information` | 尚缺的信息或能力 | 空列表表示没有缺失 |
| `next_steps` | 修复、验证或后续动作 | 恢复消费并验证追平 |

## 3. 完整 Case 示例

```json
{
  "context": {
    "case_id": "sg-event-delay",
    "created_at": "2026-07-12T10:00:00+08:00",
    "raw_input": "SG ClickHouse event 表数据缺失，下游统计明显变少",
    "normalized_symptom": "event data missing",
    "environment": "production",
    "time_range": "最近一小时",
    "entities": {
      "region": "sg",
      "system": "clickhouse",
      "table": "event"
    },
    "user_supplied": {}
  },
  "report": {
    "case_id": "sg-event-delay",
    "status": "resolved",
    "conclusion": "消费任务积压导致 event 数据延迟落入 ClickHouse",
    "confidence": "confirmed",
    "route": {
      "candidates": [],
      "selected_skill_id": "diagnose-ck-not-correct"
    },
    "skill_id": "diagnose-ck-not-correct",
    "skill_version": "1.0.0",
    "evidence": [
      {
        "summary": "consumer lag 持续升高",
        "source": "clickhouse-readonly"
      }
    ],
    "missing_information": [],
    "next_steps": [
      "恢复消费任务",
      "验证 event 数据追平"
    ]
  }
}
```

## 4. SQLite 知识库结构

知识库包含 `cases` 和 `case_chunks` 两张核心表。

### 4.1 cases 表

每个 Case 保存一行检索元数据：

| 字段 | 示例 |
| --- | --- |
| `case_id` | `sg-event-delay` |
| `created_at` | `2026-07-12T10:00:00+08:00` |
| `region` | `sg` |
| `environment` | `production` |
| `system` | `clickhouse` |
| `skill_id` | `diagnose-ck-not-correct` |
| `skill_version` | `1.0.0` |
| `status` | `resolved` |
| `conclusion` | `消费任务积压导致 event 数据延迟落入 ClickHouse` |
| `source_path` | 原始 Case JSON 的绝对路径 |
| `content_hash` | 原始 Case 规范化内容的 SHA-256 |
| `embedding_provider` | `ollama:nomic-embed-text` |

这些字段用于地区、环境和系统过滤，也用于增量更新、模型隔离和原始记录回源。

### 4.2 case_chunks 表

每个 Case 默认产生三个 chunk：

```text
<case-id>:0:summary
<case-id>:1:diagnosis
<case-id>:2:resolution
```

每个 chunk 保存：

| 字段 | 作用 |
| --- | --- |
| `chunk_id` | chunk 唯一标识 |
| `case_id` | 所属 Case |
| `chunk_type` | `summary`、`diagnosis` 或 `resolution` |
| `content` | 用于生成 embedding 的可读文本 |
| `embedding` | float32 向量的二进制数据 |
| `dimension` | 向量维度 |
| `embedding_provider` | provider 和模型标识 |
| `content_hash` | chunk 文本的 SHA-256 |

删除 `cases` 表中的 Case 时，对应 chunk 会通过外键级联删除。

## 5. Case 如何切分

### 5.1 Summary chunk

用于匹配故障现象、环境和资源：

```text
故障描述: SG ClickHouse event 表数据缺失，下游统计明显变少
规范化现象: event data missing
环境: production
时间范围: 最近一小时
实体: {"region": "sg", "system": "clickhouse", "table": "event"}
使用技能: diagnose-ck-not-correct 1.0.0
```

### 5.2 Diagnosis chunk

用于匹配历史根因和证据模式：

```text
结论: 消费任务积压导致 event 数据延迟落入 ClickHouse
置信度: confirmed
证据: [{"summary": "consumer lag 持续升高", "source": "clickhouse-readonly"}]
```

### 5.3 Resolution chunk

用于匹配历史处理办法：

```text
后续步骤: ["恢复消费任务", "验证 event 数据追平"]
用户补充: {}
```

三段文本分别生成 embedding。查询时，一个 Case 可能有多个 chunk 与问题相似，当前实现保留该 Case 得分最高的 chunk。

## 6. 哪些 Case 可以进入知识库

默认只有以下状态会建立 embedding 索引：

```text
completed
resolved
success
```

以下状态默认跳过：

```text
needs_user_input
no_matching_skill
blocked_by_incomplete_skill
```

这可以避免把“尚未调查”“没有匹配 Skill”或“流程尚未完成”错误沉淀为已验证知识。调试时可以使用 `--include-incomplete` 强制索引，但不建议用于正常知识库。

## 7. 索引过程

```text
读取原始 Case JSON
  -> 检查调查状态
  -> 生成 summary/diagnosis/resolution
  -> 计算 Case 和 chunk 的 content hash
  -> 调用 embedding provider
  -> 写入 cases 和 case_chunks
```

同一个 Case 重复索引时：

- Case 内容和 provider 均未变化：返回 `unchanged`。
- Case 内容发生变化：删除旧记录并重新生成三个 chunk。
- provider 或模型发生变化：重新生成向量。

## 8. 查询示例

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge search \
  "新加坡 event 数据因为消费积压没有及时到达" \
  --region sg \
  --environment production \
  --system clickhouse
```

示例结果：

```json
[
  {
    "case_id": "sg-event-delay",
    "score": 0.82,
    "matched_chunk": "diagnosis",
    "content": "结论: 消费任务积压导致 event 数据延迟落入 ClickHouse\n置信度: confirmed\n证据: ...",
    "skill_id": "diagnose-ck-not-correct",
    "skill_version": "1.0.0",
    "status": "resolved",
    "source_path": "/path/to/cases/sg-event-delay.json"
  }
]
```

查询结果中的 `score` 表示向量相似度，不表示根因置信度。Agent 必须打开 `source_path` 检查完整 Case，并重新验证当前故障证据。

## 9. Embedding provider

第一版提供两种 provider：

- `hashing`：零依赖、可离线运行，用于测试和近似关键词召回；不等同于高质量语义模型。
- `ollama`：调用本地 Ollama embedding 模型，用于实际语义检索。

索引和查询必须使用相同的 provider 和模型。切换模型后应执行 `rebuild` 或使用新的数据库文件，不能直接混合比较不同模型生成的向量。

## 10. 相关文档

- [系统设计](design_cn.md)
- [整体项目测试手册](project_test_guide.md)
- [Embedding 知识库测试手册](embedding_knowledge_test.md)
