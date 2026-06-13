"""C3 StatsWidget — 可视化看板：柱状图 + 标签饼图 + 专注趋势折线图。

被动刷新，不发射信号。布局：
┌─────────────────────────────────┐
│ 📊 本周番茄 (柱状图)              │
├─────────────────┬───────────────┤
│ 🏷 标签分布 (饼图)│ 📈 专注趋势   │
│                 │ [7天|30天] ▼  │
└─────────────────┴───────────────┘
"""

from datetime import date, timedelta
from collections import Counter

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from src.ui.styles import COLORS
from src.services.logger import get_logger

logger = get_logger(__name__)

# 标签饼图配色（最多 8 种，超出循环）
PIE_COLORS = [
    QColor("#4CAF50"),  # 绿
    QColor("#FF9800"),  # 橙
    QColor("#2196F3"),  # 蓝
    QColor("#9C27B0"),  # 紫
    QColor("#F44336"),  # 红
    QColor("#009688"),  # 青
    QColor("#FFC107"),  # 黄
    QColor("#795548"),  # 棕
]

# 中文星期名
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _week_range(dt: date) -> tuple[date, date]:
    """返回 dt 所在周的周一和周日。"""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# ------------------------------------------------------------------
# TagPieWidget — 自定义 QPainter 饼图
# ------------------------------------------------------------------


class TagPieWidget(QWidget):
    """用 QPainter 绘制饼图，显示标签分布百分比。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 160)
        self._data: dict[str, int] = {}  # tag → count
        self._colors: list[QColor] = []

    def update_data(self, tag_counts: dict[str, int]):
        self._data = tag_counts
        self._colors = [PIE_COLORS[i % len(PIE_COLORS)] for i in range(len(tag_counts))]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 尺寸
        w = self.width()
        h = self.height()
        margin = 8
        legend_width = 90
        pie_diameter = min(w - legend_width - margin * 3, h - margin * 2)
        pie_rect = QRectF(margin, (h - pie_diameter) / 2, pie_diameter, pie_diameter)

        data = self._data
        if not data:
            painter.setPen(QColor("#999"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无标签数据")
            painter.end()
            return

        total = sum(data.values())
        if total == 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无标签数据")
            painter.end()
            return

        # 绘制扇形
        angle = 0  # 1/16 degree units (Qt uses 1/16 degree)
        items = list(data.items())
        colors = self._colors
        for i, (tag, count) in enumerate(items):
            span = int(360 * 16 * count / total)
            color = colors[i]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.drawPie(pie_rect, angle, span)
            angle += span

        # 绘制图例
        legend_x = int(pie_rect.right()) + margin + 8
        legend_y = margin + 4
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        item_h = 20
        for i, (tag, count) in enumerate(items):
            y = legend_y + i * item_h
            pct = count / total * 100
            color = colors[i]
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(legend_x, y, 10, 10)
            painter.setPen(QColor("#ccc"))
            painter.drawText(legend_x + 16, y, legend_width - 20, 14,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             f"{tag} ({pct:.0f}%)")

        painter.end()


# ------------------------------------------------------------------
# StatsWidget
# ------------------------------------------------------------------


class StatsWidget(QWidget):
    """可视化统计看板，被动刷新，date_str 参数决定数据范围。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── 顶部标题 ──
        title = QLabel("📊 统计看板")
        title.setStyleSheet(f"color:{COLORS['grey_dark']}; font-size:15px; font-weight:bold;")
        root.addWidget(title)

        # ── 柱状图：本周每日番茄数 ──
        section1 = QLabel("🍅 本周番茄")
        section1.setStyleSheet(f"color:{COLORS['grey']}; font-size:12px;")
        root.addWidget(section1)

        self.bar_plot = pg.PlotWidget()
        self.bar_plot.setBackground(COLORS.get("white", "#ffffff"))
        self.bar_plot.setMinimumHeight(180)
        self.bar_plot.showGrid(x=False, y=True, alpha=0.3)
        self.bar_plot.getAxis("left").setPen(pg.mkPen(color=COLORS.get("grey_light", "#9e9e9e")))
        self.bar_plot.getAxis("bottom").setPen(pg.mkPen(color=COLORS.get("grey_light", "#9e9e9e")))
        self.bar_plot.getAxis("left").setTextPen(pg.mkPen(color=COLORS.get("grey", "#757575")))
        self.bar_plot.getAxis("bottom").setTextPen(pg.mkPen(color=COLORS.get("grey", "#757575")))
        self.bar_plot.setLabel("left", "番茄数")
        root.addWidget(self.bar_plot, 1)

        # ── 下半部分：饼图 | 折线图 ──
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        section2 = QLabel("🏷 标签分布")
        section2.setStyleSheet(f"color:{COLORS['grey']}; font-size:12px;")
        left_col.addWidget(section2)
        self.pie_widget = TagPieWidget()
        self.pie_widget.setStyleSheet(f"background:{COLORS.get('white', '#ffffff')}; border-radius:6px;")
        left_col.addWidget(self.pie_widget, 1)
        bottom.addLayout(left_col, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        trend_header = QHBoxLayout()
        section3 = QLabel("📈 专注趋势")
        section3.setStyleSheet(f"color:{COLORS['grey']}; font-size:12px;")
        trend_header.addWidget(section3)
        trend_header.addStretch()
        self.range_combo = QComboBox()
        self.range_combo.addItems(["7 天", "30 天"])
        self.range_combo.setCurrentIndex(0)
        self.range_combo.setStyleSheet(
            f"background:{COLORS.get('white', '#ffffff')}; color:{COLORS.get('grey_dark', '#333')}; "
            "border:1px solid #555; border-radius:4px; padding:2px 6px; font-size:11px;"
        )
        self.range_combo.currentIndexChanged.connect(lambda: self._refresh_trend(self._last_date_str))
        trend_header.addWidget(self.range_combo)
        right_col.addLayout(trend_header)

        self.line_plot = pg.PlotWidget()
        self.line_plot.setBackground(COLORS.get("white", "#ffffff"))
        self.line_plot.showGrid(x=True, y=True, alpha=0.3)
        self.line_plot.getAxis("left").setPen(pg.mkPen(color=COLORS.get("grey_light", "#9e9e9e")))
        self.line_plot.getAxis("bottom").setPen(pg.mkPen(color=COLORS.get("grey_light", "#9e9e9e")))
        self.line_plot.getAxis("left").setTextPen(pg.mkPen(color=COLORS.get("grey", "#757575")))
        self.line_plot.getAxis("bottom").setTextPen(pg.mkPen(color=COLORS.get("grey", "#757575")))
        self.line_plot.setLabel("left", "分钟")
        right_col.addWidget(self.line_plot, 1)
        bottom.addLayout(right_col, 4)

        root.addLayout(bottom, 2)

        self._last_date_str = ""

    # ── Public ────────────────────────────────────────────

    def refresh(self, date_str: str):
        """被动刷新：根据选中日期更新三个图表。"""
        self._last_date_str = date_str
        dt = date.fromisoformat(date_str)
        monday, sunday = _week_range(dt)

        # 柱状图：本周
        self._refresh_bar(dt)

        # 饼图：本周标签分布（与柱状图范围一致）
        self._refresh_pie(monday.isoformat(), sunday.isoformat())

        # 折线图：近 N 天
        self._refresh_trend(date_str)

    # ── 柱状图 ────────────────────────────────────────────

    def _refresh_bar(self, dt: date):
        self.bar_plot.clear()
        self.bar_plot.setTitle(None)  # 显式清除上一次的标题
        monday, sunday = _week_range(dt)
        raw = dict(self.db.get_daily_tomato_counts(monday.isoformat(), sunday.isoformat()))

        x = list(range(7))
        y = [raw.get((monday + timedelta(days=i)).isoformat(), 0) for i in range(7)]

        bg_item = pg.BarGraphItem(x=x, height=y, width=0.6, brush="#4CAF50", pen=pg.mkPen(None))
        self.bar_plot.addItem(bg_item)

        # X 轴刻度
        ticks = [(i, f"{name}\n{(monday + timedelta(days=i)).strftime('%m/%d')}")
                 for i, name in enumerate(WEEKDAY_NAMES)]
        self.bar_plot.getAxis("bottom").setTicks([ticks])

        # 空数据占位
        if sum(y) == 0:
            self.bar_plot.setTitle("本周暂无数据", color="#888", size="12pt")

    # ── 饼图 ──────────────────────────────────────────────

    def _refresh_pie(self, start_date: str, end_date: str):
        entries = self.db.get_entries_by_date_range(start_date, end_date)
        tag_counter: Counter[str] = Counter()
        for e in entries:
            for tag in e.get("tags", []):
                tag_counter[tag] += 1
        self.pie_widget.update_data(dict(tag_counter))

    # ── 折线图 ────────────────────────────────────────────

    def _refresh_trend(self, date_str: str):
        self.line_plot.clear()
        self.line_plot.setTitle(None)  # 显式清除上一次的标题
        if not date_str:
            return
        dt = date.fromisoformat(date_str)
        days = 7 if self.range_combo.currentIndex() == 0 else 30
        start = dt - timedelta(days=days - 1)
        raw = dict(self.db.get_daily_tomato_counts(start.isoformat(), dt.isoformat()))

        dates = [start + timedelta(days=i) for i in range(days)]
        y = [raw.get(d.isoformat(), 0) * 25 for d in dates]  # 番茄数 × 25 min
        x = list(range(days))

        pen = pg.mkPen(color="#2196F3", width=2)
        self.line_plot.addItem(pg.PlotDataItem(x, y, pen=pen, symbol="o", symbolSize=5, symbolBrush="#2196F3"))

        # X 轴刻度（每 2-7 天标一个避免拥挤）
        step = max(1, days // 7)
        ticks = [(i, d.strftime("%m/%d")) for i, d in enumerate(dates) if i % step == 0]
        self.line_plot.getAxis("bottom").setTicks([ticks])

        if sum(y) == 0:
            self.line_plot.setTitle("暂无趋势数据", color="#888", size="12pt")
