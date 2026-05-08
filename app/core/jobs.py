import uuid
import asyncio
import json
from typing import Dict, Optional, AsyncIterator
from app.core.types import JobState, JobProgressEvent, JobResult

class InMemoryJobStore:
    def __init__(self) -> None:
        self.jobs: Dict[str, JobState] = {}
        self.queues: Dict[str, "asyncio.Queue[JobProgressEvent]"] = {}

    def create(self) -> JobState:
        job_id = uuid.uuid4().hex
        state = JobState(job_id=job_id)
        self.jobs[job_id] = state
        self.queues[job_id] = asyncio.Queue()
        return state

    def get(self, job_id: str) -> Optional[JobState]:
        return self.jobs.get(job_id)

    async def push(self, job_id: str, evt: JobProgressEvent) -> None:
        await self.queues[job_id].put(evt)

    async def sse_stream(self, job_id: str) -> AsyncIterator[JobProgressEvent]:
        q = self.queues[job_id]
        while True:
            evt = await q.get()
            yield evt
            # Cortamos por el propio evento, no por el status
            if evt.step in ("done", "error"):
               break

    async def sse_lines(self, job_id: str) -> AsyncIterator[str]:
        async for evt in self.sse_stream(job_id):
            data = evt.model_dump(exclude_none=True, mode="json")
            yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        
    def set_running(self, job_id: str) -> None:
        self.jobs[job_id].status = "running"

    def set_done(self, job_id: str, result: JobResult) -> None:
        self.jobs[job_id].status = "done"
        self.jobs[job_id].result = result

    def set_error(self, job_id: str, err: str) -> None:
        self.jobs[job_id].status = "error"
        self.jobs[job_id].error = err
