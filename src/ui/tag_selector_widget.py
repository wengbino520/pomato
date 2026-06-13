"""可复用标签多选按钮组。

供 PopupWindow / EditEntryDialog / AddEntryDialog 共用，
统一标签选择体验：点击按钮切换，支持多选。
"""

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from src.services.logger import get_logger

logger = get_logger(__name__)


class TagSelectorWidget(QWidget):
    """标签多选按钮组，被动组件，父窗口通过 selected_tags() 读取结果。"""

    def __init__(self, tags: list[str], selected: list[str] | None = None,
                 parent=None):
        super().__init__(parent)
        self._tag_buttons: dict[str, QPushButton] = {}
        self._selected: list[str] = []
        self._tag_list: list[str] = list(tags)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for tag in tags:
            btn = QPushButton(tag)
            btn.setStyleSheet(self._tag_style(False))
            btn.clicked.connect(lambda _checked, t=tag, b=btn: self._toggle(t, b))
            layout.addWidget(btn)
            self._tag_buttons[tag] = btn

        layout.addStretch()

        # Pre-select
        if selected:
            self.select_tags(selected)

    # ── Public API ──────────────────────────────────────────

    def selected_tags(self) -> list[str]:
        """Return currently selected tag names (in selection order)."""
        return list(self._selected)

    def select_tags(self, tags: list[str]):
        """Pre-select a list of tags (ignores unknown names)."""
        for tag in tags:
            if tag in self._tag_buttons and tag not in self._selected:
                self._selected.append(tag)
                self._tag_buttons[tag].setStyleSheet(self._tag_style(True))
        if tags:
            logger.debug("TagSelector: pre-selected %s", [t for t in tags if t in self._tag_buttons])

    @property
    def tag_list(self) -> list[str]:
        """Ordered list of all tag names (for Ctrl+1~9 shortcuts)."""
        return self._tag_list

    @property
    def tag_buttons(self) -> dict[str, QPushButton]:
        """Dict of tag name → button (for shortcut handlers)."""
        return self._tag_buttons

    # ── Internal ────────────────────────────────────────────

    def _toggle(self, tag: str, btn: QPushButton):
        if tag in self._selected:
            self._selected.remove(tag)
            btn.setStyleSheet(self._tag_style(False))
        else:
            self._selected.append(tag)
            btn.setStyleSheet(self._tag_style(True))

    @staticmethod
    def _tag_style(selected: bool) -> str:
        if selected:
            return (
                "QPushButton {"
                "  background:#ef5350; color:white;"
                "  border:1.5px solid #ef5350; border-radius:12px;"
                "  padding:3px 10px; font-size:12px;"
                "}"
            )
        return (
            "QPushButton {"
            "  background:white; color:#555;"
            "  border:1.5px solid #ddd; border-radius:12px;"
            "  padding:3px 10px; font-size:12px;"
            "}"
            "QPushButton:hover { border-color:#ef5350; color:#ef5350; }"
        )
