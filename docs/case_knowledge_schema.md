# Case 与知识库数据结构

本文说明一个 Oncall Case 如何从原始 JSON 转换为本地 embedding 知识库记录，以及查询结果如何回到原始证据。

## 1. 为什么保存历史 Case

Skill 和历史 Case 解决的问题不同：

| 内容 | Skill | 历史 Case |
| --- | --- | --- |
| 本质 | 标准排查流程 | 某次真实故障记录 |
| 回答的问题 | 应该怎么查 | 以前类似问题发生过什么 |
| 保存内容 | 步骤、工具、证据要求、停止条件 | 现象、环境、证据、根因、处理结果 |
| 复用方式 | 执行同一套流程 | 提供相似案例线索 |
| 稳定性 | 相对稳定 | 时效性和环境相关性较强 |

例如，Skill 可能规定：

```text
1. 检查消费延迟
2. 比较源端和 ClickHouse 数量
3. 检查任务状态
4. 验证数据是否追平
```

历史 Case 则记录某次实际执行结果：

```text
SG event 表数据缺失
consumer lag 持续升高
根因是消费任务积压
重启任务并回补后恢复
```

因此，仅保留 Skill 也可以完成故障排查，包括选择流程、收集上下文、查询当前系统和根据当前证据判断根因。历史 Case 不是执行 Skill 的必要条件。

保存历史 Case 主要增加以下能力：

- 检索相似历史故障。
- 判断同类问题以前是否发生过。
- 参考历史根因、证据特征和处理动作。
- 查看某个 Skill 在真实场景中的执行记录。
- 根据历史执行效果改进 Skill。
- 支持复盘、趋势统计和审计。

历史 Case 也需要维护：过期结论可能误导当前排查，记录可能包含敏感信息，相似案例可能让 Agent 过早锁定根因，embedding 索引也会产生额外成本。当 Case 数量很少时，语义检索的收益可能有限。

本项目将 Skill 作为长期核心资产，将历史 Case 知识库作为可选增强。即使检索到相似 Case，也只能把它当作调查线索；当前故障的根因仍需要按照 Skill 重新获取证据并验证。

## 2. 数据存放位置

原始 Case 保存在：

```text
cases/<case-id>.json
```

embedding 知识库默认保存在：

```text
knowledge/knowledge.db
```

`knowledge.db` 是本地 SQLite 数据库，用于保存检索元数据、可读文本片段和 embedding 向量。原始 Case JSON 是事实源，知识库通过 `source_path` 指回原始文件。`cases/` 和 `knowledge/` 默认都不提交 Git。

## 3. 原始 Case JSON

一个 Case 由 `context` 和 `report` 两部分组成。

### 3.1 Context

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

### 3.2 Report

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

## 4. 完整 Case 示例

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

## 5. SQLite 知识库结构

知识库包含 `cases` 和 `case_chunks` 两张核心表。

### 5.1 cases 表

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

### 5.2 case_chunks 表

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

## 6. Case 如何切分

Case chunk 是从一个完整历史 Case 中提取的一段语义集中的可搜索文本。它不会把一个 Case 变成三个独立 Case，而是为同一个 Case 建立三张用途不同的检索卡片：

```text
一个完整历史 Case
├── summary chunk：发生了什么
├── diagnosis chunk：为什么发生、证据是什么
└── resolution chunk：当时如何处理
```

可以简单理解为：

```text
原始 Case = 完整故障档案
Chunk = 档案中的可搜索卡片
Embedding = 卡片在向量空间中的语义坐标
```

完整 Case 同时包含故障现象、环境、调查证据、根因和处理方法。如果把所有内容拼成一个长文本只生成一个 embedding，不同信息可能互相稀释。例如，“SG event 表数据缺失”主要应该匹配故障现象，而“consumer lag 升高后如何恢复”主要应该匹配根因和解决方法。拆分后，每个 chunk 只表达一类信息，可以提高匹配精度。

### 6.1 Summary chunk

用于匹配故障现象、环境和资源：

```text
故障描述: SG ClickHouse event 表数据缺失，下游统计明显变少
规范化现象: event data missing
环境: production
时间范围: 最近一小时
实体: {"region": "sg", "system": "clickhouse", "table": "event"}
使用技能: diagnose-ck-not-correct 1.0.0
```

适合匹配：

```text
SG event 数据不完整
ClickHouse event 表缺数据
生产环境事件数量变少
```

### 6.2 Diagnosis chunk

用于匹配历史根因和证据模式：

```text
结论: 消费任务积压导致 event 数据延迟落入 ClickHouse
置信度: confirmed
证据: [{"summary": "consumer lag 持续升高", "source": "clickhouse-readonly"}]
```

适合匹配：

```text
消费积压导致 CK 数据延迟
consumer lag 一直升高
数据为什么没有及时写入
```

### 6.3 Resolution chunk

用于匹配历史处理办法：

```text
后续步骤: ["恢复消费任务", "验证 event 数据追平"]
用户补充: {}
```

适合匹配：

```text
消费任务积压怎么恢复
event 数据延迟如何处理
恢复后应该怎么验证
```

三段文本分别生成 embedding，并保存为三条 `case_chunks` 记录：

```text
sg-event-delay:0:summary
sg-event-delay:1:diagnosis
sg-event-delay:2:resolution
```

三条记录都通过同一个 `case_id` 指向完整原始 Case。查询时，一个 Case 可能有多个 chunk 与问题相似，当前实现会按 `case_id` 聚合，并为每个 Case 保留得分最高的 chunk。

例如，查询：

```text
新加坡 event 数据因为消费积压没有及时到达
```

可能主要命中 `diagnosis` chunk。`matched_chunk: diagnosis` 只表示这个 Case 的根因和证据部分与查询最相似；系统仍需通过 `source_path` 打开完整 Case，读取完整上下文、路由、证据和处理结果。

## 7. 哪些 Case 可以进入知识库

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

## 8. 索引过程

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

## 9. 查询示例

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

### 9.1 查询命中后读取的完整原始 Case

Chunk 只用于定位相关 Case。查询命中 `sg-event-delay` 后，Agent 最终读取的是 `source_path` 指向的完整 JSON，例如：

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

完整 Case 提供 Chunk 中没有完整呈现的调查上下文。Agent 可以参考它寻找调查方向，但仍需要对当前故障重新执行 Skill 并获取当前证据。

## 10. Embedding provider

第一版提供两种 provider：

- `hashing`：零依赖、可离线运行，用于测试和近似关键词召回；不等同于高质量语义模型。
- `ollama`：调用本地 Ollama embedding 模型，用于实际语义检索。

索引和查询必须使用相同的 provider 和模型。切换模型后应执行 `rebuild` 或使用新的数据库文件，不能直接混合比较不同模型生成的向量。

## 11. 相关文档

- [系统设计](design_cn.md)
- [整体项目测试手册](project_test_guide.md)
- [Embedding 知识库测试手册](embedding_knowledge_test.md)
