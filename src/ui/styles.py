"""
UI 样式常量 (CD-03) —— 统一管理颜色与常用样式片段。

用法:
    from src.ui.styles import COLORS, STYLES
    btn.setStyleSheet(STYLES["btn_primary"])
    label.setStyleSheet(f"color:{COLORS['primary']};")
"""

# ── 颜色调色板 ───────────────────────────────────────────────────────

COLORS = {
    "primary": "#ef5350",
    "primary_dark": "#d84343",
    "primary_light": "#ffebee",
    "green": "#66bb6a",
    "orange": "#e65100",
    "brown": "#5d4037",
    "brown_light": "#efebe9",
    "grey": "#757575",
    "grey_dark": "#333",
    "grey_medium": "#666",
    "grey_light": "#9e9e9e",
    "grey_bg": "#fafafa",
    "grey_border": "#ddd",
    "grey_border_light": "#eee",
    "white": "white",
    "white_translucent": "rgba(255,255,255,0.85)",
    "white_hover": "rgba(255,255,255,0.2)",
    "orange_bg": "#fff3e0",
    "orange_border": "#ffe0b2",
    "page_bg": "#f8f8f8",
    "disabled_bg": "#e0e0e0",
    "blue": "#1976d2",
    "priority_high": "#ef5350",
    "priority_med": "#ff9800",
    "priority_low": "#9e9e9e",
    "delete_red": "#c62828",
    "dark_blue": "#1565c0",
    "dark_green": "#388e3c",
}

# ── 按钮样式模板 ─────────────────────────────────────────────────────

def btn_style(color: str, *, text_color: str = "white", padding: str = "8px 20px") -> str:
    """生成按钮样式字符串 (CD-03)。"""
    return (
        f"QPushButton {{ background:{color}; color:{text_color}; border:none;"
        f"  border-radius:5px; padding:{padding}; font-size:13px; }}"
        f"QPushButton:hover {{ border:1px solid rgba(255,255,255,0.5); }}"
        f"QPushButton:disabled {{ background:#ccc; }}"
    )


# ── 常用样式片段 ─────────────────────────────────────────────────────

STYLES = {
    # 按钮
    "btn_primary": btn_style(COLORS["primary"]),
    "btn_grey": btn_style(COLORS["grey"]),
    "btn_brown": btn_style(COLORS["brown"]),
    "btn_blue": btn_style(COLORS["blue"]),
    "btn_green": btn_style(COLORS["green"]),
    "btn_dark_green": btn_style(COLORS["dark_green"]),
    "btn_dark_blue": btn_style(COLORS["dark_blue"]),
    "btn_grey_light": btn_style(COLORS["grey_light"]),
    "btn_history": (
        "QPushButton { background:#ef5350; color:white; border:none;"
        "  border-radius:5px; padding:8px 20px; font-size:13px; }"
        "QPushButton:hover { border:1px solid rgba(255,255,255,0.5); }"
        "QPushButton:disabled { background:#e0e0e0; color:#9e9e9e; border:1px solid #e0e0e0; }"
    ),
    # 文本输入框
    "text_edit": (
        "QTextEdit { border:1.5px solid #ddd; border-radius:6px; padding:8px;"
        "  font-size:13px; background:#fafafa; }"
        "QTextEdit:focus { border-color:#ef5350; background:white; }"
    ),
    # 红色标记标签
    "tag_default": (
        "QPushButton { border:1.5px solid #ddd; border-radius:12px;"
        "  padding:5px 14px; font-size:12px; background:white; }"
        "QPushButton:hover { border-color:#ef5350; color:#ef5350; }"
    ),
    "tag_selected": (
        "QPushButton { background:#ef5350; color:white;"
        "  border:1.5px solid #ef5350; border-radius:12px;"
        "  padding:5px 14px; font-size:12px; }"
    ),
    # 箭头按钮
    "arrow_btn": (
        "QPushButton { background:transparent; color:white; border:none;"
        "  font-size:16px; padding:4px 6px; }"
        "QPushButton:hover { background:rgba(255,255,255,0.2); border-radius:4px; }"
    ),
    # Header 栏
    "header_bar": "background:#ef5350;",
    # 统计栏
    "stats_bar": "background:#fff3e0; border-bottom:1px solid #ffe0b2;",
    # Tab 面板
    "tab_widget": "QTabWidget::pane { border:none; } QTabBar::tab { padding:6px 18px; font-size:13px; }",
    # 底部操作栏
    "bottom_bar": "background:white; border-top:1px solid #eee;",
    # 滚动区域
    "scroll_area": "QScrollArea { border:none; background:#f8f8f8; }",
    # 条目框架
    "entry_frame": (
        "QFrame { background:white; border:1px solid #e0e0e0;"
        "  border-radius:6px; padding:10px; margin-bottom:2px; }"
        "QFrame:hover { border-color:#ef5350; }"
    ),
}


