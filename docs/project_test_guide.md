# oncall_cli 整体项目测试手册

本文用于验证从用户输入到 Skill 路由、上下文交互、Case 保存、Claude Code 接入和历史知识检索的完整链路。

## 1. 测试范围

| 编号 | 模块 | 验证目标 |
| --- | --- | --- |
| T01 | 项目环境 | Python 包和 CLI 能正常启动 |
| T02 | Skill 注册 | 能发现并校验业务 Skill |
| T03 | 路由成功 | CK 数据异常能路由到预期 Skill |
| T04 | 上下文补充 | 缺少环境和时间范围时能询问用户 |
| T05 | 无匹配路由 | 不相关问题不会误选 CK Skill |
| T06 | 安全停止 | draft Skill 不会伪造调查结论 |
| T07 | Case 持久化 | 输入、路由、证据和结果写入 JSON |
| T08 | Claude Code | 项目指令和原生入口 Skill 配置正确 |
| T09 | 知识索引 | 已解决 Case 能增量写入 embedding 索引 |
| T10 | 语义检索 | 能召回相关历史 Case 并返回原始路径 |
| T11 | 过滤与隔离 | 地区过滤、未完成状态和模型隔离有效 |
| T12 | 索引维护 | 重建、状态和删除命令正常工作 |

## 2. 自动化测试

在项目根目录执行：

```bash
PYTHONPYCACHEPREFIX=/tmp/oncall-cli-pycache \
PYTHONPATH=src \
python3 -m pytest -q -p no:cacheprovider
```

预期所有测试通过。当前测试文件包括：

- `tests/test_registry.py`：Skill 发现、清单解析与错误处理。
- `tests/test_router.py`：输入规范化、确定性评分、歧义和无匹配。
- `tests/test_cli_flow.py`：上下文问询、安全停止和 Case 保存。
- `tests/test_claude_integration.py`：`CLAUDE.md` 与 `.claude/skills` 契约。
- `tests/test_knowledge.py`：embedding 索引、查询、过滤、重建和删除。

## 3. CLI 基础验证

### T01：帮助信息与模块入口

```bash
PYTHONPATH=src python3 -m oncall_cli --help
PYTHONPATH=src python3 -m oncall_cli knowledge --help
```

预期：

- 第一条显示 Oncall CLI 参数。
- 第二条显示 `index`、`rebuild`、`search`、`delete` 和 `status` 子命令。
- 命令退出码为 0。

### T02：Skill 注册表

```bash
find skills -name skill.yaml -o -name SKILL.md
PYTHONPATH=src python3 -m pytest -q tests/test_registry.py -p no:cacheprovider
```

预期发现 `diagnose-ck-not-correct`，测试通过且没有 Skill 加载错误。

## 4. 路由与交互测试

为避免测试数据写入项目目录，以下命令统一使用临时 Case 目录：

```bash
rm -rf /tmp/oncall-cli-project-cases
mkdir -p /tmp/oncall-cli-project-cases
```

### T03：明确的 CK 数据异常

```bash
PYTHONPATH=src python3 -m oncall_cli \
  --cases-root /tmp/oncall-cli-project-cases \
  "发现一个oncall，现象是：线上 CK 数据不对，排查最近一小时"
```

预期输出包含：

```text
已路由: diagnose-ck-not-correct
调查状态: blocked_by_incomplete_skill
尚未执行任何 CK 调查
```

该结果表示路由成功，但不是根因排查成功。

### T04：缺少必要上下文

启动交互命令：

```bash
PYTHONPATH=src python3 -m oncall_cli \
  --cases-root /tmp/oncall-cli-project-cases \
  "CK 数据不一致"
```

按提示输入：

```text
production
最近一小时
```

预期：

- CLI 只询问环境和时间范围。
- 补充完成后继续同一个 Case。
- 最终因 Skill 是 draft 而安全停止。
- 保存的 JSON 中 `user_supplied` 包含两个回答。

### T05：不相关问题不得误路由

```bash
PYTHONPATH=src python3 -m oncall_cli \
  --cases-root /tmp/oncall-cli-project-cases \
  "Java 服务启动失败"
```

预期输出：

```text
调查状态: no_matching_skill
没有找到可靠匹配的 skill
```

不得出现 `diagnose-ck-not-correct` 已选中的结论。

### T06：泛化描述不得猜测

```bash
PYTHONPATH=src python3 -m oncall_cli \
  --cases-root /tmp/oncall-cli-project-cases \
  "发现一个oncall，现象是：XXX，帮我排查原因"
```

预期返回 `no_matching_skill`，并要求补充系统、具体现象、环境和时间范围。

## 5. Case 持久化验证

### T07：检查保存内容

先完成 T03，然后执行：

```bash
ls -1 /tmp/oncall-cli-project-cases
python3 -m json.tool /tmp/oncall-cli-project-cases/<case-id>.json
```

检查 JSON 至少包含：

- `context.case_id`、`raw_input`、`environment` 和 `time_range`。
- `report.status`、`skill_id` 和 `skill_version`。
- `report.route` 及可读路由原因。
- `report.evidence`、`missing_information` 和 `next_steps`。

预期 `context.case_id` 与 `report.case_id` 一致。

## 6. Claude Code 集成验证

### T08：静态配置验证

```bash
test -f CLAUDE.md
test -f .claude/skills/oncall-investigation/SKILL.md
PYTHONPATH=src python3 -m pytest -q \
  tests/test_claude_integration.py \
  -p no:cacheprovider
```

预期测试通过。`CLAUDE.md` 应要求 Claude：

- 保留用户原始描述。
- 运行 Python CLI。
- 由 Python registry 选择业务 Skill。
- 遇到 draft 或缺少工具时停止。
- 不把路由证据当作根因证据。

### T08.1：Claude Code 手工测试

在项目根目录启动：

```bash
claude
```

可先执行 `/memory`，确认根目录 `CLAUDE.md` 已加载，然后输入：

```text
发现一个oncall，现象是：线上 SG CK event 表数据不对，排查最近一小时，帮我排查原因。
```

预期 Claude Code：

1. 选择 `oncall-investigation` 项目 Skill。
2. 运行 `PYTHONPATH=src python3 -m oncall_cli "<原始描述>"`。
3. 展示 Python registry 选择的 `diagnose-ck-not-correct`。
4. 因业务 Skill 尚未完成而停止，不生成 CK 查询或根因。

注意：Claude Code 会把提示和必要项目上下文发送给外部模型服务。只在符合数据安全要求的环境执行本测试。

## 7. Embedding 知识库验证

详细样例 JSON 和逐条命令参见 [Embedding 知识库测试手册](embedding_knowledge_test.md)。整体项目验收至少执行以下步骤。

### T09：重建索引

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  rebuild --cases-root /tmp/oncall-embedding-cases
```

预期 resolved Case 显示 `indexed`，未完成 Case 显示 `skipped`。

### T10：语义查询和回源

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  search "SG event 消费数据没有及时到达" --limit 5
```

检查结果包含：

- `case_id`
- `score`
- `matched_chunk`
- `skill_id` 和 `skill_version`
- `source_path`

使用 `source_path` 打开原始 Case，确认返回内容可回源，而不是只存在于生成摘要中。

### T11：地区过滤与未完成 Case 隔离

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  search "配置同步失败" --region eu
```

预期只返回 EU Case。执行 `status` 后，Case 数量不应包含默认跳过的 `blocked_by_incomplete_skill` Case。

### T12：状态、增量更新和删除

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  status

PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  index /tmp/oncall-embedding-cases/sg-event-delay.json

PYTHONPATH=src python3 -m oncall_cli knowledge \
  --database /tmp/oncall-project-knowledge.db \
  --provider hashing \
  delete sg-event-delay
```

预期未修改 Case 返回 `unchanged`，删除返回 `deleted`，随后 `status` 的 Case 和 chunk 数量相应减少。

## 8. 完整验收标准

- 所有自动化测试通过。
- CLI 和知识库帮助命令正常。
- 明确 CK 故障能路由，泛化或不相关故障不会误路由。
- 缺失上下文会询问用户并保存回答。
- draft Skill 必须安全停止，不声称已执行调查。
- Case JSON 能完整记录输入、路由、证据和状态。
- Claude Code 通过项目 Skill 调用 Python registry，而不是自行选择业务 Skill。
- 只有符合状态要求的 Case 默认进入 embedding 索引。
- embedding 查询支持回源、地区过滤、增量更新、重建和删除。
- 使用真实语义模型时，索引和查询固定使用相同 provider/model。
- 历史 Case 只作为调查线索，当前根因仍需新的证据验证。

## 9. 当前已知边界

- `diagnose-ck-not-correct` 仍为 draft，不能真正查询 CK 或得出根因。
- 默认 hashing provider 主要用于离线验证，不等同于高质量语义模型。
- Ollama provider 已接入，但需要本机另行启动 Ollama 并准备 embedding 模型。
- 当前 SQLite 使用 Python 暴力余弦计算，适合本地少量 Case；大规模升级路径见设计文档。
