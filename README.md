# oncall_cli

`oncall_cli` 是一个本地、基于技能路由的 Oncall 调查 CLI 骨架。它接收自然语言故障描述，匹配技能，收集必要上下文，并把调查报告保存为本地 JSON。

## 当前能力边界

当前版本已经支持：

- 扫描并校验 `skills` 目录中的技能清单。
- 根据系统和现象进行确定性路由，并解释路由原因。
- 询问缺失的环境、时间范围等必要上下文。
- 将案例、路由证据和报告保存到 `cases` 目录。
- 使用本地 embedding 和 SQLite 对已解决 Case 建立语义索引。
- 在无匹配技能或技能流程未完成时安全停止，不虚构根因。

当前只提供一个 `diagnose-ck-not-correct` 示例技能，而且它仍处于 `draft` 状态。该技能可以识别 ClickHouse 数据缺失、不一致、延迟或错误等描述，但 `SKILL.md` 中尚未实现调查步骤，也没有 ClickHouse、MySQL、TCC 或代码仓库连接工具。因此，成功路由不代表已经执行根因排查。

## 历史 Case 语义知识库

知识库默认位于 `knowledge/knowledge.db`，该目录不会提交 Git。每个 Case 被切分为 `summary`、`diagnosis` 和 `resolution` 三个向量片段。默认只索引状态为 `completed`、`resolved` 或 `success` 的 Case，避免把未完成调查当作已验证知识。

### Embedding provider

零依赖离线模式默认使用 `hashing` provider：

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge status
```

它适合测试和近似关键词召回，但不是高质量语义模型。实际中文语义检索建议运行本地 Ollama embedding 模型：

```bash
export ONCALL_EMBEDDING_PROVIDER=ollama
export ONCALL_EMBEDDING_MODEL=nomic-embed-text
```

也可以在每条命令中显式使用 `--provider ollama --model <model>`。索引和查询必须使用相同的 provider/model；切换模型后执行 `rebuild`。

### 索引和更新一个 Case

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge index \
  cases/<case-id>.json
```

相同内容重复索引会返回 `unchanged`。Case 内容或 provider 改变后会自动重新生成 embedding。

### 重建索引

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge rebuild \
  --cases-root cases
```

如需调试未完成 Case，可以显式增加 `--include-incomplete`；正常知识库不建议使用该参数。

### 语义查询

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge search \
  "SG event 表数据消费延迟"
```

可以增加结构化过滤条件，但召回和排序仍由 embedding 相似度完成：

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge search \
  "event 表数据不完整" \
  --region sg \
  --environment production \
  --system clickhouse \
  --limit 5
```

结果包含 Case ID、相似度、匹配片段、Skill 版本和原始 Case 路径。历史结果只是调查线索，仍需重新验证当前证据。

### 状态和删除

```bash
PYTHONPATH=src python3 -m oncall_cli knowledge status
PYTHONPATH=src python3 -m oncall_cli knowledge delete <case-id>
```

完整测试样例和操作步骤参见 [Embedding 知识库测试手册](docs/embedding_knowledge_test.md)。

## 通过 Python CLI 使用

### 单次调用

在项目根目录执行：

```bash
PYTHONPATH=src python3 -m oncall_cli \
  "发现一个oncall,现象是: 线上 CK 数据不对，排查最近一小时 帮我排查原因"
```

当前示例会路由到 `diagnose-ck-not-correct`，然后以 `blocked_by_incomplete_skill` 状态停止，并明确说明尚未执行 CK 调查。

如果描述过于泛化，例如：

```bash
PYTHONPATH=src python3 -m oncall_cli \
  "发现一个oncall,现象是: XXX 帮我排查原因"
```

系统无法获得足够的系统和现象信号，将返回 `no_matching_skill`，并提示补充受影响系统、具体现象、环境和时间范围。

### 交互模式

启动交互模式：

```bash
PYTHONPATH=src python3 -m oncall_cli
```

看到 `oncall>` 提示符后输入故障描述。输入 `exit` 或 `quit` 退出。

### 安装后使用命令

安装项目后，也可以直接使用项目命令：

```bash
oncall_cli "线上 CK 数据不对，排查最近一小时"
```

## 在 Claude Code 中使用

项目已经提供 `CLAUDE.md` 和 `.claude/skills/oncall-investigation/SKILL.md`。在项目根目录启动 Claude Code：

```bash
cd /Users/frank/frank_project/oncall_cli
claude
```

然后可以直接输入：

```text
发现一个oncall，现象是：线上 SG CK event 表数据不对，帮我排查原因。
```

Claude Code 会通过项目 Skill 调用 Python CLI。Python registry 扫描 `skills/*/skill.yaml` 并选择业务 Skill；Claude 不应绕过 registry 自行猜测。

对应的实际命令仍然是：

```bash
PYTHONPATH=src python3 -m oncall_cli \
  "发现一个oncall,现象是: 线上 CK 数据不对，排查最近一小时"
```

当前 `diagnose-ck-not-correct` 仍是 `draft`，因此 Claude Code 目前只会完成路由、上下文收集和报告保存，然后安全停止。只有补全业务 `SKILL.md` 的只读调查流程并接入受控工具网关后，才能真正执行数据查询和根因调查。

可以在 Claude Code 中运行 `/memory`，确认根目录 `CLAUDE.md` 已加载。项目 Skill 是否被选中取决于其 `description` 与用户请求是否匹配。

## 验证

运行测试：

```bash
PYTHONPATH=src python3 -m pytest -q
```

详细架构与系统分层参见：

- [英文设计文档](docs/design.md)
- [中文设计文档](docs/design_cn.md)
- [整体项目测试手册](docs/project_test_guide.md)
- [Embedding 知识库测试手册](docs/embedding_knowledge_test.md)
