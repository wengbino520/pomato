# C4 弹窗体验优化 — 设计方案

> **日期**: 2026-06-14 | **优先级**: 🟢 P2 | **预估**: 3-4 小时

---

## 1. 用户故事

### US-01: 上一轮上下文提醒
> 优先级: P2

**作为** 番茄钟用户，
**我希望** 番茄完成弹窗顶部显示上一轮的工作内容摘要，
**以便** 快速回忆刚才做了什么，决定是继续还是切换任务，无需手动点"重复上一条"。

**验收标准**：
- [ ] Given 上一轮有记录 "登录模块代码审查", When 番茄结束弹窗出现, Then 顶部显示 `上一轮：登录模块代码审查`
- [ ] Given 今天是第一个番茄钟, When 弹窗出现, Then 不显示上一轮信息（或显示 "今天第一个番茄钟 🍅"）
- [ ] Given 上一轮被跳过, When 弹窗出现, Then 显示再上一轮的有效记录（跳过被跳过的）

---

### US-02: 上一轮标签自动预选
> 优先级: P2

**作为** 番茄钟用户，
**我希望** 弹窗打开时自动勾选上一轮使用的标签，
**以便** 继续同一类工作时不需重新点选标签，让连续记录更丝滑。

**验收标准**：
- [ ] Given 上一轮使用了"开发"标签, When 弹窗打开, Then "开发"标签自动选中
- [ ] Given 上一轮使用了"开发"+"测试"两个标签, When 弹窗打开, Then 两个标签均自动选中
- [ ] Given 今天是第一个番茄钟（无上一轮）, When 弹窗打开, Then 不自动选中任何标签
- [ ] Given 上一轮被跳过, When 弹窗打开, Then 自动选中再上一条有效记录的标签

---

### US-03: 键盘快捷键高效操作
> 优先级: P2

**作为** 键盘流用户，
**我希望** 通过 `Ctrl+1~9` 快速切换标签、`Ctrl+D` 跳过、`Ctrl+S` 提交，
**以便** 双手不离开键盘即可完成番茄记录，大幅提升效率。

**验收标准**：
- [ ] Given 弹窗打开且有 6 个标签, When 按下 Ctrl+3, Then 第 3 个标签选中状态切换
- [ ] Given 弹窗打开, When 按下 Ctrl+D, Then 弹窗关闭且记录标记为跳过
- [ ] Given 弹窗打开且输入框有焦点, When 按下 Ctrl+S/Ctrl+Enter, Then 提交记录

---

### US-04: 休息结束轻柔提醒
> 优先级: P2

**作为** 番茄钟用户，
**我希望** 休息结束时收到轻柔的提醒而非系统通知轰炸，
**以便** 不被粗暴打断，有过渡感地回到工作状态。

**验收标准**：
- [ ] Given 休息结束, When 触发提醒, Then 屏幕右下角显示半透明淡入窗口（非系统 toast）
- [ ] Given 淡入窗口显示中, When 用户 10 秒未操作, Then 窗口自动淡出消失
- [ ] Given 用户点击淡入窗口, When 点击任意位置, Then 窗口消失

---

## 2. 技术架构

```
src/ui/popup_window.py     (修改)  ← US-01/02/03
src/ui/break_reminder.py   (新增)  ← US-04 休息结束淡入窗
src/app.py                 (修改)  ← US-04 替换 tray.showMessage
tests/test_popup_queue.py   (修改)  ← 新增测试
```

**不新增信号**，不新增 DB 查询（标签推荐复用 `get_latest_valid_entry`），不引入新依赖。

### 2.1 US-01 上一轮上下文

- `PopupWindow.__init__` 已接收 `previous_content` 参数
- 当前只在 "重复上一条" 按钮中使用
- **改动**：在 header 下方增加一行 `QLabel`，条件显示 `上一轮：{previous_content[:40]}...`
- 若 `previous_content` 为空，显示 `今天第一个番茄钟 🍅`

### 2.2 US-02 上一轮标签自动预选

- 复用现有链路：`app.py → get_latest_valid_entry(today)` → `previous_tags`
- **逻辑**：`_setup_ui()` 末尾调用 `_apply_tag_recommendations()`，检查 `self.previous_tags`，逐项调动 `_toggle_tag()` 预选
- `get_latest_valid_entry` 已跳过 skipped 记录 → 满足 "上一轮被跳过则取再上一条"
- 无新 DB 查询，纯 UI 层改动

### 2.3 US-03 快捷键

| 快捷键 | 操作 | 实现 |
|--------|------|------|
| `Ctrl+1` ~ `Ctrl+9` | 切换第 N 个标签 | `QShortcut(QKeySequence("Ctrl+1"), ...)` |
| `Ctrl+D` | 跳过本轮 | 已连接 `_on_skip` |
| `Ctrl+S` | 提交（额外） | 新增，作为 Ctrl+Enter 替代 |

> 标签索引从 1 开始，超出标签数量则忽略。

### 2.4 US-04 淡入提醒窗

- **新组件** `BreakReminderWindow(QWidget)`：
  - `WindowStaysOnTopHint | FramelessWindowHint | Tool`
  - `setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)` — 半透明必备
  - 屏幕右下角定位（`QScreen.availableGeometry()`），圆角背景 `rgba(40,40,40,220)`
  - `QPropertyAnimation` 控制 `windowOpacity` 从 0→0.95（淡入 500ms）
  - 10 秒后自动淡出（`QTimer` + 反向动画，随后 `close()` + `deleteLater()`）
  - 点击任意位置 → 停止动画 → `close()`
- **生命周期管理**（评审 ISSUE-2）：
  - `TrayManager` 新增 `self._break_reminder` 引用
  - `_on_break_ended()` 创建新窗前 `close()` + `deleteLater()` 旧窗
  - `TrayManager.__del__` 或 `app.aboutToQuit` 中清理活跃淡入窗
- **替换点**：`app.py` `_on_break_ended()` 中 `tray.showMessage(...)` → 创建并显示 `BreakReminderWindow`
- 音效无需额外处理（`_play_sound()` 在 `_show_popup` 番茄结束时已播放，休息结束本身无音效）

---

## 3. 影响范围

| 文件 | 操作 | 影响 |
|------|------|------|
| `src/ui/popup_window.py` | 修改 | +40 行（US-01 header + US-02 推荐 + US-03 快捷键） |
| `src/ui/break_reminder.py` | 新增 | ~60 行（US-04 淡入窗） |
| `src/app.py` | 修改 | ~5 行（替换 break_ended 通知） |
| `tests/test_popup_window.py` | 新增 | +3 测试（快捷键跳过、上一轮上下文、空上下文） |

**无架构变更，无新依赖，无新信号。**
