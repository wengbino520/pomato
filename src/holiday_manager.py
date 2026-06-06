"""
节假日/工作日识别模块。

数据来源：免费的中国节假日 API (https://timor.tech/api/holiday)
- 本地缓存，每天只请求一次
- API 失败时回退到简单的周一~周五判断
"""
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

HOLIDAY_API = "https://timor.tech/api/holiday/year/{year}"


class HolidayManager:
    """管理中国节假日数据，判断某一天是否为工作日。"""

    def __init__(self, data_dir: Path):
        self._cache_file = data_dir / "holiday_cache.json"
        self._cache: dict[str, dict] = {}  # date_str -> {holiday: bool, name: str}
        self._last_fetch_year: Optional[int] = None
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_workday(self, d: Optional[date] = None) -> bool:
        """判断指定日期是否为工作日。

        优先级：缓存 > API 实时查询 > weekday 回退
        """
        if d is None:
            d = date.today()
        date_str = d.isoformat()

        # 1. 检查缓存
        if date_str in self._cache:
            holiday_info = self._cache[date_str]
            # holiday=False 表示当天是工作日（需要补班）
            # holiday=True 表示当天是假日
            return not holiday_info["holiday"]

        # 2. 尝试从 API 获取当年数据
        if self._last_fetch_year != d.year:
            self._fetch_year(d.year)

        # 3. 再次检查缓存
        if date_str in self._cache:
            return not self._cache[date_str]["holiday"]

        # 4. 回退：周一~周五为工作日
        return d.weekday() < 5

    def get_holiday_name(self, d: Optional[date] = None) -> Optional[str]:
        """如果当天是节假日，返回节日名称；否则返回 None。"""
        if d is None:
            d = date.today()
        date_str = d.isoformat()
        info = self._cache.get(date_str)
        if info and info["holiday"]:
            return info.get("name")
        return None

    def force_refresh(self):
        """强制重新拉取当年节假日数据。"""
        self._fetch_year(date.today().year)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_cache(self):
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    # 验证缓存是否包含当年数据
                    self._cache = saved
                    current_year = str(date.today().year)
                    if any(k.startswith(current_year) for k in self._cache):
                        self._last_fetch_year = date.today().year
            except Exception:
                self._cache = {}

    def _save_cache(self):
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save holiday cache: %s", e)

    def _fetch_year(self, year: int):
        """从 API 获取指定年份的节假日数据。"""
        import urllib.request

        url = HOLIDAY_API.format(year=year)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "POMATO/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to fetch holiday data for %d: %s", year, e)
            return

        if not isinstance(data, dict):
            return

        # API 返回格式:
        # {
        #   "code": 0,
        #   "holiday": {
        #     "01-01": { "holiday": true, "name": "元旦", "wage": 3 },
        #     "01-28": { "holiday": true, "name": "春节", "wage": 3 },
        #     "01-26": { "holiday": false, "name": "春节调休补班", "wage": 1 },
        #     ...
        #   }
        # }
        holiday_dict = data.get("holiday") or data.get("type")
        if not isinstance(holiday_dict, dict):
            return

        for mmdd, info in holiday_dict.items():
            if not isinstance(info, dict):
                continue
            try:
                month, day = map(int, mmdd.split("-"))
                d = date(year, month, day)
                date_str = d.isoformat()
                self._cache[date_str] = {
                    "holiday": bool(info.get("holiday", False)),
                    "name": str(info.get("name", "")),
                }
            except (ValueError, TypeError):
                continue

        self._last_fetch_year = year
        self._save_cache()
        logger.info("Holiday cache updated for %d (%d entries)", year, len(holiday_dict))
