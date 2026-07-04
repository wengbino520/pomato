"""
Shared AI report generation worker (CD-04).

Consolidates the duplicated QThread pattern from ReportWindow._AIWorker
and HistoryWindow._HistoryAIWorker into a single reusable class.
"""
from PyQt6.QtCore import QThread, pyqtSignal

from src.services.ai_client import AIClient
from src.services.logger import get_logger

logger = get_logger(__name__)


class AIReportWorker(QThread):
    """Background worker for AI report generation with streaming support.

    Signals:
        chunk_received(str): Emitted for each streaming chunk of text.
        finished(str): Emitted with the full result when generation completes.
        error(str): Emitted with error message if generation fails.
    """
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ai_client: AIClient, entries: list[dict], report_date: str,
                 todos: list[dict] | None = None, period: str = "daily"):
        super().__init__()
        self.ai_client = ai_client
        self.entries = entries
        self.report_date = report_date
        self.todos = todos or []
        self.period = period

    def run(self):
        try:
            result = self.ai_client.generate_report(
                self.entries,
                self.report_date,
                on_chunk=lambda c: self.chunk_received.emit(c),
                todos=self.todos if self.todos else None,
                period=self.period,
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("AI report generation failed: date=%s, period=%s",
                             self.report_date, self.period)
            self.error.emit(str(exc))
