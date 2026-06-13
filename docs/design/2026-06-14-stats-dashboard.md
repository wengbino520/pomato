# C3 可视化看板 — 设计方案

> **日期**: 2026-06-14 | **优先级**: 🟡 P1 | **预估**: 4-5 小时

---

## 1. 用户故事

### US-01: 查看本周番茄产出趋势
> 优先级: P1

**作为** 番茄钟用户，
**我希望** 在统计 Tab 中看到一个本周每日番茄数的柱状图，
**以便** 一眼看出本周哪天效率高、哪天摸鱼了，激励自己保持节奏。

**验收标准**：
- [ ] Given 本周有至少一天的番茄记录, When 打开统计 Tab, Then 柱状图显示周一至周日每天完成数，缺失日期显示 0
- [ ] Given 本周无任何番茄记录, When 打开统计 Tab, Then 图表区域显示 "本周暂无数据" 占位提示
- [ ] Given 今天是周日, When 打开统计 Tab, Then 本周范围正确（周一至周日），不跨周

---

### US-02: 查看标签分布了解时间投向
> 优先级: P1

**作为** 番茄钟用户，
**我希望** 在统计 Tab 中看到当前查看日期的标签分布饼图，
**以便** 了解今天的时间花在了哪些类型的工作上（开发/测试/会议/…）。

**验收标准**：
- [ ] Given 今天有 3 条番茄记录(开发×2, 测试×1), When 查看今天的统计, Then 饼图显示开发 67%、测试 33%
- [ ] Given 用户通过日期导航切换到 6 月 10 日, When 查看统计 Tab, Then 饼图自动更新为该日期的标签分布
- [ ] Given 某天无标签记录, When 查看该天统计, Then 饼图区域显示 "暂无标签数据"

---

### US-03: 查看专注时长趋势
> 优先级: P1

**作为** 番茄钟用户，
**我希望** 看到近 7 天（或 30 天）的每日专注分钟数折线图，
**以便** 评估近期工作强度变化，判断是否需要调整节奏。

**验收标准**：
- [ ] Given 近 7 天有番茄记录, When 打开统计 Tab, Then 折线图显示每日专注分钟数
- [ ] Given 用户切换到 30 天视图, When 下拉选择 "30 天", Then 折线图数据范围切换为近 30 天
- [ ] Given 某天无记录, When 绘制折线图, Then 该天显示为 0 分钟（不跳过）

---

## 2. 技术选型

- **`pyqtgraph`** — 纯 Python / PyQt 原生 / 轻量 ~2MB / 高性能
- 安装：`pip install pyqtgraph` → 追加到 `requirements.txt`

## 3. 架构分层

```
src/ui/stats_widget.py  (新增)  ← L3 展示层
src/core/database.py    (修改)  ← L1 新增 1 个查询方法
tests/test_database.py   (修改)  ← 新增测试
```

**不新增信号**，`StatsWidget` 通过 `refresh(date_str)` 被动刷新。

### 3.1 数据库新增方法 (`database.py`)

| 方法 | SQL | 返回 |
|------|-----|------|
| `get_daily_tomato_counts(start_date, end_date)` | `SELECT date, COUNT(*) FROM pomodoro_entries WHERE date BETWEEN ? AND ? AND skipped=0 GROUP BY date ORDER BY date` | `[(date_str, count), ...]` |

> 标签分布和专注趋势复用同一查询 + Python 侧计算（避免过度抽象 DB 层）。

### 3.2 `StatsWidget` 布局

```
┌─────────────────────────────────────────────────┐
│ 📊 本周番茄                                     │
│  [柱状图: 周一8 周二6 周三10 周四5 周五7 ...]     │
├────────────────────────┬────────────────────────┤
│ 📊 标签分布             │ 📊 专注趋势             │
│  [饼图]                 │ [折线图]      [7天 ▾]  │
│  (跟随当前查看日期)     │                        │
└────────────────────────┴────────────────────────┘
```

### 3.3 `main_window.py` 集成

- `_build_tabs()` 新增第 4 个 Tab："📊 统计"
- `refresh()` 末尾调用 `self._stats_widget.refresh(date_str)`

---

## 4. 任务清单

> 详见 → `docs/design/2026-06-14-stats-dashboard-tasks.md`

| 检查点 | TASK | 内容 |
|--------|------|------|
| CP-1 DB 层 | C3-01 | `get_daily_tomato_counts()` + 测试 |
| CP-2 组件 | C3-02 | 创建 `StatsWidget`（3 图表） |
| CP-3 集成 | C3-03 | 集成到 MainWindow + 全量回归 + 路线图更新 |
