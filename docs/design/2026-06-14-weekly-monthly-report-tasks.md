# D2 周报/月报生成 开发任务清单

> 创建时间: 2026-06-14  
> 总预估: 3-4 小时（约 7 个子任务）  
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：零依赖基础设施（可并行）

### TASK-01: database.py — `get_todos_by_date_range()` + 测试
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/core/database.py`, `tests/test_database_todos.py`
- **操作**: 新增方法，参数化查询，返回 `list[dict]`，支持 end_date 日期的未完成任务累积
- **验证**: `pytest tests/test_database_todos.py -q`
- **预计**: 20 分钟

### TASK-02: ai_client.py — `build_prompt()` 增加 `period` 参数
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/services/ai_client.py`, `tests/test_ai_client.py`
- **操作**: `build_prompt()` 加 `period="daily"` 参数，按 daily/weekly/monthly 生成不同 Prompt 前缀和统计措辞
- **验证**: `pytest tests/test_ai_client.py -q`
- **预计**: 25 分钟

---

## 第二层：UI 层（依赖 TASK-01, TASK-02）

### TASK-03: report_window.py — 周期选择器 + 日期范围标签
- **状态**: ✅ 已完成
- **依赖**: 无（UI 布局可先行，生成时才需要 DB/API）
- **文件**: `src/ui/report_window.py`
- **操作**: 
  1. 添加 `_get_period_range()` 工具函数
  2. header 区域增加 `QComboBox`（日报/周报/月报）+ 日期范围 `QLabel`
  3. 周期切换时更新日期标签、更新 `self.entries`
  4. `_generate_fallback()` 按周期自适应
- **验证**: `pytest tests/test_report_window.py -q`
- **预计**: 40 分钟

### TASK-04: report_window.py — 周期化 AI 生成 + 测试
- **状态**: ✅ 已完成
- **依赖**: TASK-02, TASK-03
- **文件**: `src/ui/report_window.py`, `tests/test_report_window.py`
- **操作**:
  1. `_AIWorker` 增加 `period` 参数，透传到 `ai_client.generate_report()`
  2. `ReportWindow._start_generation()` 传入当前 period
  3. 周报/月报不自动 `save_report`（key 策略待定）
- **验证**: `pytest tests/test_report_window.py -q`
- **预计**: 25 分钟

---

## 第三层：集成回归

### TASK-05: 全量回归
- **状态**: ✅ 已完成
- **依赖**: TASK-01~04
- **操作**: `pytest tests/ -v` 确认 0 regression
- **预计**: 5 分钟

---

## 检查点恢复指南

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 基础设施就绪 | TASK-01, TASK-02 完成 | `TASK-01` ~ `TASK-02` |
| CP-2 UI 改造完成 | TASK-03, TASK-04 完成 | `TASK-03` ~ `TASK-04` |
| CP-3 集成完成 | TASK-05 通过 | `TASK-05` |
