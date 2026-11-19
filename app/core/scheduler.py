"""APScheduler wrapper.

Two kinds of jobs are scheduled here:

1. Recurring workflow triggers (from `WorkflowSchedule` rows) — e.g.
   "run the monthly payroll workflow on the 1st of every month".
2. One-off "resume" jobs for Delay nodes — e.g. "resume execution #42
   at 2026-06-22T10:00:00".

Uses `BackgroundScheduler` so it runs its own thread independent of the
PyQt event loop. Each job callback opens its own DB session via the
service layer, so it's safe to call from the scheduler thread.
"""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger


class SchedulerService:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    # ------------------------------------------------------------------
    # Recurring workflow triggers
    # ------------------------------------------------------------------
    def add_recurring_workflow_trigger(self, schedule_id: int, workflow_id: int,
                                        trigger_type: str, trigger_args: dict) -> str:
        """Register a recurring job that starts a new execution of `workflow_id`.

        `trigger_type` is "interval" (trigger_args like {"hours": 24}) or
        "cron" (trigger_args like {"hour": 9, "minute": 0, "day": 1}).
        Returns the APScheduler job id.
        """
        if trigger_type == "interval":
            trigger = IntervalTrigger(**trigger_args)
        elif trigger_type == "cron":
            trigger = CronTrigger(**trigger_args)
        else:
            raise ValueError(f"Unknown trigger_type '{trigger_type}'")

        job_id = f"workflow_schedule_{schedule_id}"
        self._scheduler.add_job(
            func=_run_scheduled_workflow,
            trigger=trigger,
            args=[workflow_id],
            id=job_id,
            replace_existing=True,
        )
        return job_id

    def remove_job(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    # ------------------------------------------------------------------
    # One-off delay-node resumes
    # ------------------------------------------------------------------
    def schedule_delay_resume(self, execution_id: int, run_at: datetime) -> str:
        job_id = f"resume_execution_{execution_id}_{run_at.timestamp()}"
        self._scheduler.add_job(
            func=_resume_execution_after_delay,
            trigger=DateTrigger(run_date=run_at),
            args=[execution_id],
            id=job_id,
            replace_existing=True,
        )
        return job_id


# ----------------------------------------------------------------------
# Module-level callbacks (must be picklable / importable for APScheduler)
# ----------------------------------------------------------------------
def _run_scheduled_workflow(workflow_id: int) -> None:
    from app.services import execution_service

    execution_service.start_execution(workflow_id=workflow_id, started_by_id=None, context={})


def _resume_execution_after_delay(execution_id: int) -> None:
    from app.core.engine.executor import ExecutionEngine

    ExecutionEngine().resume_after_delay(execution_id)


# Singleton instance used across the app
scheduler_service = SchedulerService()
