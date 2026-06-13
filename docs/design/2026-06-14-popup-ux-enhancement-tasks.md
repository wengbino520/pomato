# C4 弹窗体验优化 开发任务清单

> 创建时间: 2026-06-14 | 总预估: 3-4 小时 | 4 个子任务

---

## TASK-01: US-01 上一轮上下文 + US-03 快捷键
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/ui/popup_window.py`
- **操作**:
  1. header 下方增加上一轮上下文 QLabel（条件渲染）
  2. Ctrl+1~9 快捷键绑定标签切换
  3. Ctrl+D 跳过、Ctrl+S 提交
- **验证**: 手动启动弹窗 → 上一轮显示 → Ctrl+3 切换标签 → Ctrl+D 跳过
- **预计**: 45 分钟

---

## TASK-02: US-02 上一轮标签自动预选
- **状态**: ✅ 已完成
- **依赖**: TASK-01
- **文件**: `src/ui/popup_window.py`
- **操作**:
  1. `_apply_tag_recommendations()` — 检查 `self.previous_tags`，逐项调动 `_toggle_tag()`
  2. `get_latest_valid_entry` 已跳过 skipped → 满足 "上一轮被跳过取再上一条"
  3. 无新 DB 查询
- **验证**: 手动创建一条带标签的记录 → 下个番茄弹窗 → 标签自动选中
- **预计**: 30 分钟

---

## TASK-03: US-04 休息结束淡入提醒窗
- **状态**: ✅ 已完成
- **依赖**: TASK-02
- **文件**: `src/ui/break_reminder.py` (新增), `src/app.py` (修改)
- **操作**:
  1. `BreakReminderWindow` — 半透明 + WA_TranslucentBackground、右下角定位、淡入动画
  2. 10 秒后反向动画淡出 → `close()` + `deleteLater()`
  3. 点击任意位置 → 停止动画 → 关闭
  4. `TrayManager` 维护 `self._break_reminder` 引用，创建前清理旧窗
  5. `app.py` `_on_break_ended()` 替换 `tray.showMessage`
- **验证**: 等待休息结束 → 淡入窗口出现 → 点击消失 / 10 秒自动消失
- **预计**: 60 分钟

---

## TASK-04: 测试 + 回归 + 路线图
- **状态**: ✅ 已完成
- **依赖**: TASK-03
- **文件**: `tests/test_popup_window.py` (新增), `docs/evolution-roadmap.md`
- **操作**:
  1. 新增 3 个测试（快捷键跳过、上一轮上下文显示、空上下文不显示）
  2. `pytest tests/ -q --tb=short` 全量确认
  2. `pytest tests/ -q --tb=short` 全量确认
  3. 手动冒烟：4 项改进逐项验证
  4. 更新路线图 — C4 标记 ✅、M2 标记完整
- **预计**: 30 分钟

---

## 检查点

| 检查点 | 完成条件 | commit |
|--------|---------|--------|
| CP-1 上下文+快捷键 | TASK-01 | `TASK-01` |
| CP-2 标签预选 | TASK-02 | `TASK-02` |
| CP-3 淡入窗 | TASK-03 | `TASK-03` |
| 🏁 全部完成 | TASK-04 | `TASK-04` |
