# 任务清单模板（依赖排序 · 可断点续传）

> 来源：`AGENTS.md` 管线 ① 方案设计

---

## 模板

```markdown
# <功能名称> 开发任务清单（依赖排序 · 可断点续传）

> 创建时间: YYYY-MM-DD
> 总预估: X 天（约 N 个子任务）
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：零依赖基础设施（可并行）

### TASK-01: <任务标题>
- **状态**: ⬜ 未开始 / 🔄 进行中 / ✅ 已完成
- **依赖**: 无
- **文件**: `src/xxx.py`
- **操作**: 具体做什么
- **验证**: 如何确认完成
- **预计**: X 分钟

---

## 检查点恢复指南

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 xxx就绪 | TASK-01~04 完成 | `TASK-01` ~ `TASK-04` |
| CP-2 xxx就绪 | TASK-05~07 完成 | `TASK-05` ~ `TASK-07` |
```

---

---

## 真实示例

以下是一个完整的 TASK 示例（来自本项目 F7-07 待办-番茄双向关联）：

```markdown
### TASK-03: database.py — add_entry() 增加 todo_id 参数
- **状态**: ✅ 已完成
- **依赖**: TASK-01 (ALTER TABLE 迁移)
- **文件**: `src/core/database.py`, `tests/test_database.py`
- **操作**:
  1. `add_entry()` 签名新增 `todo_id=None`
  2. INSERT 语句加入 `todo_id` 字段
  3. `get_entries_by_date()` LEFT JOIN todos 带回 `todo_title`
- **验证**:
  - `test_add_entry_with_todo_id` — 传入 todo_id 后查询可关联回 todo
  - `test_add_entry_without_todo_id` — 不传时 todo_id 为 NULL 不崩溃
- **预计**: 30 分钟
```

---

## 关键约定

| 约定 | 说明 |
|------|------|
| 状态标记 | 每个 TASK 前用 ⬜/🔄/✅ 标记进度，随时可读 |
| 依赖声明 | 每个 TASK 明确依赖哪个 TASK，决定执行顺序 |
| 分层组织 | 按架构层级分组（L1 基础设施 → L2 服务 → L3 UI → L4 集成） |
| 检查点 | 每层完成作为一个检查点，支持断点后继续 |
| commit 标记 | 每个 TASK 完成后 git commit，以 `TASK-NN` 结尾，便于回溯 |

---

## 检查点恢复

- 文档更新后即可中断，下次从下一检查点继续
- 检查点恢复：找到最后一个 ✅ 的 CP，从下一个 CP 的第一个 TASK 开始
- 小改动可精简为简短段落，大功能按模板完整输出
