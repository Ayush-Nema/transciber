"""SSE (Server-Sent Events) manager for broadcasting progress updates."""
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE connections per job."""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Subscribe to updates for a job."""
        queue: asyncio.Queue = asyncio.Queue()
        if job_id not in self._queues:
            self._queues[job_id] = []
        self._queues[job_id].append(queue)
        logger.info(f"SSE subscriber added for job {job_id}")
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Unsubscribe from job updates."""
        if job_id in self._queues:
            self._queues[job_id] = [q for q in self._queues[job_id] if q is not queue]
            if not self._queues[job_id]:
                del self._queues[job_id]

    async def publish(self, job_id: str, event_type: str, data: dict):
        """Publish an event to all subscribers of a job."""
        if job_id not in self._queues:
            return

        message = {
            "event": event_type,
            "data": data,
        }

        for queue in self._queues[job_id]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"SSE queue full for job {job_id}")

    async def event_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        """Generate SSE events for a job."""
        queue = self.subscribe(job_id)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = message["event"]
                    data = json.dumps(message["data"])
                    yield f"event: {event_type}\ndata: {data}\n\n"

                    # Stop on terminal events
                    if event_type in ("completed", "error"):
                        break

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

        finally:
            self.unsubscribe(job_id, queue)


# Singleton instance
sse_manager = SSEManager()
