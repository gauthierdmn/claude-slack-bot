import asyncio
import logging
from collections.abc import Awaitable, Callable

logger: logging.Logger = logging.getLogger(__name__)


class SessionStore:
    """
    In-memory mapping of Slack threads to Claude session IDs.

    Each unique (channel, thread_ts) pair maps to a single Claude session,
    allowing multi-turn conversations within a Slack thread.  No lock is
    needed because the bot runs on a single asyncio event loop.
    """

    def __init__(self) -> None:
        """
        Initialize an empty session store.
        """

        self._sessions: dict[tuple[str, str], str] = {}

    def get(self, channel: str, thread_ts: str) -> str | None:
        """
        Look up the Claude session ID for a Slack thread.

        Args:
            channel (str): The Slack channel ID.
            thread_ts (str): The Slack thread timestamp.

        Returns:
            str | None: The session ID, or None if no session exists.
        """

        return self._sessions.get((channel, thread_ts)

    def set(self, channel: str, thread_ts: str, session_id: str) -> None:
        """
        Store a Claude session ID for a Slack thread.

        Args:
            channel (str): The Slack channel ID.
            thread_ts (str): The Slack thread timestamp.
            session_id (str): The Claude session ID to store.
        """

        self._sessions[(channel, thread_ts)] = session_id


class SessionQueue:
    """
    Per-session async job queue ensuring serial execution within a session.

    When a job is enqueued for a session key that has no active consumer,
    a new consumer task is spawned.  The consumer pulls jobs one at a time,
    guaranteeing that concurrent messages in the same Slack thread never
    race on the same Claude session.  Idle queues are cleaned up
    automatically once the consumer drains.
    """

    def __init__(self) -> None:
        """
        Initialize an empty queue manager.
        """

        self._queues: dict[
            tuple[str, str],
            asyncio.Queue[Callable[[], Awaitable[None]]],
        ] = {}
        self._consumers: dict[tuple[str, str], asyncio.Task[None]] = {}

    async def enqueue(
        self,
        channel: str,
        thread_ts: str,
        job: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Enqueue an async job for serial execution within a session.

        If no consumer task exists for the given session key, one is
        spawned automatically.

        Args:
            channel (str): The Slack channel ID.
            thread_ts (str): The Slack thread timestamp.
            job (Callable[[], Awaitable[None]]): A zero-argument async
                callable to execute.
        """

        key: tuple[str, str] = (channel, thread_ts)

        if key not in self._queues:
            self._queues[key] = asyncio.Queue()

        await self._queues[key].put(job)

        if key not in self._consumers or self._consumers[key].done():
            self._consumers[key] = asyncio.create_task(self._consume(key))

    async def _consume(self, key: tuple[str, str]) -> None:
        """
        Consume jobs from the queue for a specific session key.

        Runs until the queue is empty, then cleans up.

        Args:
            key (tuple[str, str]): The (channel, thread_ts) session key.
        """

        queue: asyncio.Queue[Callable[[], Awaitable[None]]] = self._queues[key]

        while not queue.empty():
            job: Callable[[], Awaitable[None]] = await queue.get()

            try:
                await job()
            except Exception:
                logger.exception(
                    "Job failed for session %s",
                    key,
                )

        del self._queues[key]
        del self._consumers[key]
