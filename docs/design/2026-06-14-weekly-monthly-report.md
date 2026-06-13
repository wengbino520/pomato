# D2：周报 / 月报生成

> 创建时间: 2026-06-14  
> 状态: 设计阶段  
> 基于: `docs/evolution-roadmap.md` § D2  
> 优先级: 🔴 P0

---

## 背景

当前仅支持日报（单日），缺少周期性总结能力。用户需要按周/月汇总多个工作日的数据，生成趋势对比和阶段性总结。

---

## 用户故事

### US-01: 周期选择
> 优先级: P0

**作为** POMATO 用户，
**我希望** 在生成报告时可以选择日报/周报/月报，
**以便** 获得不同时间粒度的总结。

**验收标准**：
- [ ] Given 打开报告窗口, When 页面加载, Then 顶部显示周期下拉框，默认"日报"
- [ ] Given 选择"周报", When 下拉框变更, Then 日期范围标签更新为"本周 (周一 ~ 周日)"
- [ ] Given 选择"月报", When 下拉框变更, Then 日期范围标签更新为"本月 (6/1 ~ 6/30)"
- [ ] Given 选择"周报", When 点击生成, Then 查询本周所有非跳过条目
- [ ] Given 选择"月报", When 点击生成, Then 查询本月所有非跳过条目

### US-02: AI Prompt 差异化
> 优先级: P1

**作为** POMATO 用户，
**我希望** 周报/月报的 AI 生成内容结构不同于日报，
**以便** 周报侧重于成果总结和下周计划，月报侧重于里程碑回顾和趋势。

**验收标准**：
- [ ] Given 日报, When AI 生成, Then Prompt 中包含"按工作类型分类汇总" + "今日统计"
- [ ] Given 周报, When AI 生成, Then Prompt 中包含"本周成果总结" + "下周计划" + "趋势对比"
- [ ] Given 月报, When AI 生成, Then Prompt 中包含"月度关键产出" + "里程碑回顾" + "数据趋势"

### US-03: 周期统计数据
> 优先级: P1

**作为** POMATO 用户，
**我希望** 周报/月报中自动附带统计摘要（总番茄数、总专注时长、待办完成率），
**以便** 无需手动计算。

**验收标准**：
- [ ] Given 周报, When 生成 Prompt, Then 注入"本周共完成 N 个番茄钟，约 M 分钟，待办完成率 X%"
- [ ] Given 月报, When 生成 Prompt, Then 注入"本月共完成 N 个番茄钟，约 M 分钟，待办完成率 X%"
- [ ] Given 周报, When 回退展示, Then fallback 文本包含周期统计

---

## 技术方案

### 变更文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/ui/report_window.py` | 修改 | 增加周期选择器 + 日期范围查询 |
| `src/services/ai_client.py` | 修改 | `build_prompt()` 增加 `period` 参数 |
| `src/core/database.py` | 修改 | 新增 `get_todos_by_date_range()` |
| `tests/test_report_window.py` | 修改 | 新增周期选择 + 范围查询测试 |
| `tests/test_ai_client.py` | 修改 | 新增周报/月报 prompt 测试 |
| `tests/test_database.py` | 修改 | 新增 `get_todos_by_date_range()` 测试 |

### ReportWindow 改造

```
┌──────────────────────────────────────────┐
│ 📋 生成报告                               │
│ 周期: [周报 ▾]   日期范围: 6/8 ~ 6/14    │ ← 新增
├──────────────────────────────────────────┤
│                                          │
│  (AI 流式输出的 Markdown 编辑器)           │
│                                          │
├──────────────────────────────────────────┤
│ [🔄 重新生成]    [📋 复制] [💾 MD] [📄 Word] [关闭] │
└──────────────────────────────────────────┘
```

**周期计算逻辑**：

```python
from datetime import date, timedelta

def _get_period_range(dt: date, period: str) -> tuple[date, date]:
    if period == "daily":
        return dt, dt
    elif period == "weekly":
        monday = dt - timedelta(days=dt.weekday())
        return monday, monday + timedelta(days=6)
    elif period == "monthly":
        first = dt.replace(day=1)
        # last day of month
        if dt.month == 12:
            last = dt.replace(year=dt.year+1, month=1, day=1) - timedelta(days=1)
        else:
            last = dt.replace(month=dt.month+1, day=1) - timedelta(days=1)
        return first, last
    raise ValueError(f"Unknown period: {period}")
```

### 数据库变更

新增 `get_todos_by_date_range(start_date, end_date)`：

```sql
SELECT * FROM todos
WHERE todo_date BETWEEN ? AND ?
   OR (todo_date < ? AND status != 'done')  -- 今日视图积累逻辑（到 end_date 为止的未完成）
ORDER BY priority DESC, sort_order ASC
```

### AI Prompt 差异化

`build_prompt()` 签名变更：
```python
def build_prompt(entries, report_date=None, todos=None, period="daily") -> str:
```

Period 参数控制 Prompt 前缀和统计措辞：

| period | Prompt 前缀 | 统计措辞 |
|--------|------------|---------|
| `daily` | "日期：{date}" | "今日共完成 N 个番茄钟" |
| `weekly` | "周期：{start} ~ {end}" | "本周共完成 N 个番茄钟，约 M 分钟专注工作" |
| `monthly` | "周期：{start} ~ {end}" | "本月共完成 N 个番茄钟，约 M 分钟专注工作" |

System prompt 通过 `period` 参数注入差异化指令（在 `generate_report()` 中动态构建 messages）。

---

## 测试策略

| 测试层级 | 覆盖内容 | 预计新增 |
|----------|---------|---------|
| 单元 — DB | `get_todos_by_date_range()` 正常路径 + 空范围 + 跨越今日累积 | 3 |
| 单元 — AI | `build_prompt()` daily/weekly/monthly 三种 period 输出差异 | 3 |
| 单元 — UI | `_get_period_range()` 工具函数 | 3 |
| 组件 — UI | ReportWindow 周期选择器切换 + 日期标签更新 + fallback 文本 | 4 |
| 回归 | 现有日报功能不受影响 | — |

---

## 风险

| 风险 | 缓解 |
|------|------|
| 月报跨月份天数计算 | 使用 `date.replace()` 标准方法，不用 `calendar.monthrange` |
| `save_report` 按单日 key，周报/月报保存冲突 | 周报/月报暂时不自动 `save_report`（或使用 `{period}_{date}` 作为 key） |
| 大量条目（月报 30 天）Prompt 过长 | `_AIWorker.run()` 中不做额外截断，由用户配置的 AI model 限制自行处理 |

---

## 任务清单

见 `docs/design/2026-06-14-weekly-monthly-report-tasks.md`
