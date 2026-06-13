# D2-B：周报/月报落库 & 历史查看

> 创建时间: 2026-06-14
> 状态: 设计中
> 基于: `docs/design/2026-06-14-weekly-monthly-report.md`（D2 周报/月报生成）
> 优先级: 🔴 P0

---

## 背景

D2 实现了周报/月报的前端生成（周期选择器 + Prompt 差异化），但存在两个缺口：
1. **不落库**：周报/月报生成后不调用 `save_report()`，刷新即丢失
2. **不可回看**：历史窗口只能看日报，无法查看生成过的周报或月报

本方案补齐这两个能力。

---

## 用户故事

### US-01：周报/月报自动保存
> 优先级：P0

**作为** POMATO 用户，
**我希望** 生成的周报和月报自动存入数据库，
**以便** 关闭窗口后不会丢失。

**验收标准**：
- [ ] Given 生成周报, When AI 生成完成, Then 自动保存到 `daily_reports` 表（period="weekly", date=周一）
- [ ] Given 生成月报, When AI 生成完成, Then 自动保存到 `daily_reports` 表（period="monthly", date=1日）
- [ ] Given 导出 Markdown/Word, When 导出成功, Then 同时调用 `save_report()` 保存最终内容
- [ ] Given 同一天的生成了日报+周报+月报, When 都保存, Then 三条记录共存互不覆盖

### US-02：历史窗口查看周报/月报
> 优先级：P0

**作为** POMATO 用户，
**我希望** 在历史窗口中看到所有周期的报告（日/周/月），
**以便** 回顾不同粒度的总结。

**验收标准**：
- [ ] Given 进入历史窗口, When 加载日期列表, Then 同一天的报告以不同 badge 展示（日/周/月）
- [ ] Given 选择周报项, When 预览渲染, Then 展示该周报内容
- [ ] Given 选择月报项, When 预览渲染, Then 展示该月报内容
- [ ] Given 顶部下拉框选择"周报", When 列表刷新, Then 仅展示周报

---

## 技术方案

### 1. 数据库 Migration

```sql
-- 变更前
date TEXT UNIQUE NOT NULL

-- 变更后
date    TEXT NOT NULL,
period  TEXT NOT NULL DEFAULT 'daily',
UNIQUE(date, period)
```

| period | date 语义 | 示例 |
|--------|----------|------|
| `daily` | 当天 | `2026-06-14` |
| `weekly` | 本周一 | `2026-06-08` |
| `monthly` | 本月1日 | `2026-06-01` |

Migration 写法（幂等）：现有行 `period` 为 `NULL` → UPDATE 为 `'daily'`。

### 2. `database.py` 变更

```python
def save_report(self, date_str, raw_entries, period="daily",
                ai_summary=None, final_report=None):
    # INSERT ON CONFLICT(date, period) DO UPDATE …

def get_report(self, date_str, period="daily"):
    # SELECT … WHERE date=? AND period=?

def get_all_report_dates(self):
    # 改为返回 [(date, period), …]，语义不变（合并所有已生成日报的日期）
    # 内部 SELECT DISTINCT date, period
```

### 3. `ReportWindow` 变更

```python
# _on_finished() — 删除 if self._period == "daily": 守卫
save_date = self._start_date.isoformat()
self.db.save_report(save_date, self.entries, period=self._period,
                    ai_summary=result, final_report=result)

# _export_markdown() / _export_docx() — 导出时也保存
self.db.save_report(self._start_date.isoformat(), self.entries,
                    period=self._period, final_report=markdown)
```

### 4. `HistoryWindow` 变更

```
┌──────────────────────────────────────────────┐
│ 📚  历史报告                   [全部 ▾] 🔍   │
├──────────────┬───────────────────────────────┤
│              │                               │
│ 06/01 [月]   │  # 工作报告 · 06/01 ~ 06/30   │
│ 06/08 [周]   │                               │
│ 06/14 [日]   │  (报告内容预览)                 │
│ 06/13 [日]   │                               │
│              │                               │
└──────────────┴───────────────────────────────┘
```

- 左侧日期列表每行追加周期徽标 `[日]`/`[周]`/`[月]`
- 顶部新增 `QComboBox`：全部 / 日报 / 周报 / 月报
- 同一日期如有多个周期报告，各占一行
- `_load_dates()` 改为 `SELECT DISTINCT date, period FROM daily_reports ORDER BY date DESC`
- AI 总结按钮：仅日报支持生成（周报/月报在历史窗口不支持重新生成）

### 5. 变更文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/core/database.py` | 修改 | migration + `period` 参数 |
| `src/ui/report_window.py` | 修改 | 去掉 `if daily` 守卫，`save_date` 改为 `_start_date` |
| `src/ui/history_window.py` | 修改 | 周期徽标 + 筛选下拉 + 多周期支持 |
| `src/app.py` | 修改 | `main_window` 传新增回调 |
| `tests/test_database.py` | 修改 | `period` 相关测试 |
| `tests/test_report_window.py` | 修改 | 验证周报/月报保存行为 |
| `tests/test_history_window.py` | 新增 | 历史窗口周期筛选测试 |

---

## 测试策略

| 层级 | 覆盖内容 | 预计新增 |
|------|---------|---------|
| 单元 — DB | migration 幂等、`save_report` period 参数、`get_report` period 过滤、`get_all_report_dates` 返双列 | 5 |
| 单元 — DB | 同一 date 三个 period 共存不冲突 | 2 |
| 组件 — ReportWindow | 周报 AI 完成后调 `save_report`（period="weekly"） | 2 |
| 组件 — HistoryWindow | 周期徽标渲染、周期筛选下拉 | 4 |
| 回归 | 全量 438 → ≥450 | — |

---

## 风险

| 风险 | 缓解 |
|------|------|
| `save_report` 调用处散落 4 处（`_on_finished` + `_export_markdown` + `_export_docx` + `HistoryWindow`） | 全部统一传 `period` 参数，缺省 `"daily"` 保持兼容 |
| 历史窗口加载变慢（同一日期多条记录） | 一日期最多 3 行，列表量级不变 |
| 旧数据库升级失败 | Migration 幂等：`try: ALTER TABLE ADD period … except: pass` |

---

## 任务清单

见 `docs/design/2026-06-14-weekly-monthly-report-persistence-tasks.md`
