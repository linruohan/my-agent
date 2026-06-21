"""搜索缓存会话统计。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CacheSessionStats:
    lookups: int = 0
    hits: int = 0
    misses: int = 0
    saves: int = 0

    @property
    def hit_rate(self) -> float:
        if self.lookups <= 0:
            return 0.0
        return self.hits / self.lookups

    def as_dict(self) -> dict[str, float | int]:
        return {
            "lookups": self.lookups,
            "hits": self.hits,
            "misses": self.misses,
            "saves": self.saves,
            "hit_rate": round(self.hit_rate * 100, 1),
        }
