# C3 可视化看板 开发任务清单（依赖排序 · 可断点续传）

> 创建时间: 2026-06-14
> 总预估: 3-4 小时（5 个子任务）
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：L1 基础设施 — 已完成

### ✅ TASK-01: 安装 pyqtgraph + 更新 requirements.txt
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `requirements.txt`, `.venv`
- **操作**: `pip install pyqtgraph`, 追加到 `requirements.txt`
- **验证**: `python -c "import pyqtgraph"` 无报错
- **预计**: 5 分钟

---

## 第二层：L1 数据库 — 查询方法

### ✅ TASK-02: database.py — `get_daily_tomato_counts()` + 测试
- **状态**: ✅ 已完成
- **依赖**: TASK-01 (pyqtgraph 就绪，但 DB 层独立)
- **文件**: `src/core/database.py`, `tests/test_database.py`
- **操作**:
  1. `get_daily_tomato_counts(start_date, end_date)` — 按日期范围返回每日番茄数
  2. 标签分布和专注趋势在 Python 侧用同一查询计算
  3. 新增 4 个测试用例
- **验证**:
  - `test_get_daily_tomato_counts_normal` — 多天 + 混合数据
  - `test_get_daily_tomato_counts_excludes_skipped` — 跳过不计入
  - `test_get_daily_tomato_counts_empty_range` — 无数据返回空列表
  - `test_get_daily_tomato_counts_parameterized` — 单天查询
- **预计**: 30 分钟

---

## 第三层：L3 展示 — StatsWidget

### ✅ TASK-03: 创建 StatsWidget 组件（3 图表）
- **状态**: ✅ 已完成
- **依赖**: TASK-02 (DB 查询方法)
- **文件**: `src/ui/stats_widget.py` (新增)
- **操作**:
  1. 柱状图 (`BarGraphItem`) — 本周每日番茄数，X 轴周一→周日
  2. 饼图 (自定义 `QPainter` 绘制) — 当天标签分布百分比
  3. 折线图 (`PlotDataItem`) — 近 7/30 天专注时长趋势，含 QComboBox 切换
  4. 空数据占位提示（`QLabel` 叠加）
- **验证**:
  - 手动启动 app，打开统计 Tab，图表渲染无崩溃
  - 切换日期后饼图数据刷新
- **预计**: 90 分钟

---

## 第四层：L4 集成 — MainWindow

### ✅ TASK-04: 集成 StatsWidget 到 MainWindow 第 4 个 Tab
- **状态**: ✅ 已完成
- **依赖**: TASK-03 (StatsWidget 就绪)
- **文件**: `src/ui/main_window.py`
- **操作**:
  1. `_build_tabs()` — 新增 `📊 统计` Tab，嵌入 `StatsWidget`
  2. `refresh()` — 末尾调用 `self._stats_widget.refresh(date_str)`
  3. 无新信号，被动刷新
- **验证**: 启动 app → 点统计 Tab → 图表正确绘制，日期切换后饼图更新
- **预计**: 20 分钟

---

## 收尾

### ✅ TASK-05: 全量回归 + 路线图更新
- **状态**: ✅ 已完成
- **依赖**: TASK-04 (集成完毕)
- **文件**: `docs/evolution-roadmap.md`
- **操作**:
  1. `pytest tests/ -q --tb=short` 确认 388+ 全部通过
  2. 手动冒烟：柱状图/饼图/折线图/日期切换/空数据
  3. 更新路线图 — C3 标记 ✅ 完成
- **预计**: 15 分钟

---

## 检查点恢复指南

| 检查点 | 完成条件 | commit 标记 |
|--------|---------|-------------|
| CP-1 DB 层就绪 | TASK-02 完成 | `TASK-02` |
| CP-2 图表就绪 | TASK-03 完成 | `TASK-03` |
| CP-3 集成完毕 | TASK-04 完成 | `TASK-04` |
| 🏁 全部完成 | TASK-05 完成 | `TASK-05` |
