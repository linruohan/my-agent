"""自动化网关：定时任务调度与执行。"""

from src.automation.store import CronJobStore

__all__ = ["CronJobStore", "CronSchedulerService"]


def __getattr__(name: str):
    if name == "CronSchedulerService":
        from src.automation.scheduler import CronSchedulerService

        return CronSchedulerService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
