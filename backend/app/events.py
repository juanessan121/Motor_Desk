import asyncio
import json
from contextlib import asynccontextmanager


class EventHub:
    """Invalidaciones sin datos privados. Ejecutar un worker ASGI por instancia."""

    def __init__(self):
        self.subscribers: dict[asyncio.Queue, int] = {}

    @asynccontextmanager
    async def subscribe(self, user_id: int):
        queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.subscribers[queue] = user_id
        try:
            yield queue
        finally:
            self.subscribers.pop(queue, None)

    def publish(self, kind: str, audience: set[int] | None = None):
        payload = json.dumps({"type": kind})
        for queue, user_id in list(self.subscribers.items()):
            if audience is None or user_id in audience:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(payload)


hub = EventHub()
