# D2-B 周报/月报落库 & 历史查看 开发任务清单

> 创建时间: 2026-06-14
> 总预估: 2-3 小时（约 7 个子任务）
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：DB 层（零依赖）

### TASK-01: database.py — migration + period 参数
- **状态**: ⬜ 未开始
- **依赖**: 无
- **文件**: `src/core/database.py`, `tests/test_database.py`
- **操作**:
  1. `_init_db()`: ALTER TABLE 添加 `period` 列，UPDATE 存量行
  2. `save_report()`: 签名加 `period="daily"`，唯一键 `(date, period)`
  3. `get_report()`: 签名加 `period="daily"`
  4. `get_all_report_dates()`: 改为 SELECT DISTINCT date, period
  5. `search_reports()`/`get_reports_by_date_range()`: 适配新 schema
- **验证**: `pytest tests/test_database.py tests/test_database_todos.py -q`
- **预计**: 30 分钟

---

## 第二层：UI 层（依赖 TASK-01）

### TASK-02: report_window.py — 去掉 daily 守卫，周报/月报落库
- **状态**: ⬜ 未开始
- **依赖**: TASK-01
- **文件**: `src/ui/report_window.py`, `tests/test_report_window.py`
- **操作**:
  1. `_on_finished()`: 删除 `if self._period == "daily"`，始终保存
  2. `save_date = self._start_date.isoformat()` 作为 key
  3. `_export_markdown()`/`_export_docx()`: 导出时传 `period`
- **验证**: `pytest tests/test_report_window.py -q`
- **预计**: 15 分钟

### TASK-03: history_window.py — 周期徽标 + 筛选下拉
- **状态**: ⬜ 未开始
- **依赖**: TASK-01
- **文件**: `src/ui/history_window.py`, 新增 `tests/test_history_window.py`
- **操作**:
  1. header 增加 `QComboBox`（全部/日报/周报/月报）
  2. `_load_dates()`: 改为查询 `(date, period)` 对，每行追加周期徽标
  3. 日期列表项格式: `2026-06-14 [日]`
  4. AI 总结按钮：仅日报可用
- **验证**: `pytest tests/test_history_window.py -q`
- **预计**: 30 分钟

---

## 第三层：集成回归

### TASK-04: 全量回归
- **状态**: ⬜ 未开始
- **依赖**: TASK-01~03
- **操作**: `pytest tests/ -q` 确认 0 regression
- **预计**: 5 分钟

---

## 检查点恢复指南

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 DB 层就绪 | TASK-01 完成 | `TASK-01` |
| CP-2 UI 就绪 | TASK-02, TASK-03 完成 | `TASK-02` ~ `TASK-03` |
| CP-3 集成完成 | TASK-04 通过 | `TASK-04` |
