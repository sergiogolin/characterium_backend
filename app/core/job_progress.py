from __future__ import annotations

from dataclasses import dataclass

from app.core.jobs import InMemoryJobStore
from app.core.types import JobProgressEvent


@dataclass(frozen=True)
class IndexedProgressUpdate:
    step: str
    message_template: str
    start_pct: int = 0
    end_pct: int = 100

    async def publish(
        self,
        progress: JobProgressPublisher | None,
        *,
        index: int,
        total: int,
    ) -> None:
        if progress is None:
            return

        await progress.publish_indexed_progress(
            step=self.step,
            message_template=self.message_template,
            index=index,
            total=total,
            start_pct=self.start_pct,
            end_pct=self.end_pct,
        )


class JobProgressPublisher:
    def __init__(self, jobs: InMemoryJobStore, job_id: str) -> None:
        self.jobs = jobs
        self.job_id = job_id

    async def publish(
        self,
        *,
        step: str,
        message: str,
        pct: int | None = None,
    ) -> None:
        await self.jobs.push(
            self.job_id,
            JobProgressEvent(step=step, message=message, pct=pct),
        )

    async def publish_indexed_progress(
        self,
        *,
        step: str,
        message_template: str,
        index: int,
        total: int,
        start_pct: int = 0,
        end_pct: int = 100,
    ) -> None:
        pct = self.percent_for_index(
            index=index,
            total=total,
            start_pct=start_pct,
            end_pct=end_pct,
        )
        await self.publish(
            step=step,
            message=message_template.format(index=index, total=total),
            pct=pct,
        )

    @staticmethod
    def percent_for_index(
        *,
        index: int,
        total: int,
        start_pct: int = 0,
        end_pct: int = 100,
    ) -> int:
        if total <= 0:
            return start_pct

        bounded_index = max(0, min(index, total))
        span = end_pct - start_pct
        return start_pct + round((bounded_index / total) * span)
