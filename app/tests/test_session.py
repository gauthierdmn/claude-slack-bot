# type: ignore
import asyncio

import pytest

from claude_slack_bot.session import SessionQueue, SessionStore


class TestSessionStore:
    def test_get_returns_none_for_unknown_thread(self):
        store = SessionStore()

        assert store.get("C001", "123.456") is None

    def test_set_and_get_round_trip(self):
        store = SessionStore()

        store.set("C001", "123.456", "sess-abc")

        assert store.get("C001", "123.456") == "sess-abc"

    def test_different_threads_have_separate_sessions(self):
        store = SessionStore()

        store.set("C001", "111.000", "sess-first")
        store.set("C001", "222.000", "sess-second")

        assert store.get("C001", "111.000") == "sess-first"
        assert store.get("C001", "222.000") == "sess-second"

    def test_different_channels_have_separate_sessions(self):
        store = SessionStore()

        store.set("C001", "123.456", "sess-one")
        store.set("C002", "123.456", "sess-two")

        assert store.get("C001", "123.456") == "sess-one"
        assert store.get("C002", "123.456") == "sess-two"

    def test_set_overwrites_existing_session(self):
        store = SessionStore()

        store.set("C001", "123.456", "sess-old")
        store.set("C001", "123.456", "sess-new")

        assert store.get("C001", "123.456") == "sess-new"


class TestSessionQueue:
    @pytest.mark.asyncio
    async def test_enqueue_executes_job(self):
        queue = SessionQueue()
        executed = []

        async def job():
            executed.append(True)

        await queue.enqueue("C001", "123.456", job)
        await asyncio.sleep(0.05)

        assert executed == [True]

    @pytest.mark.asyncio
    async def test_jobs_for_same_session_run_serially(self):
        queue = SessionQueue()
        order = []

        async def make_job(label, delay):
            async def job():
                order.append(f"{label}-start")
                await asyncio.sleep(delay)
                order.append(f"{label}-end")

            return job

        job_a = await make_job("a", 0.05)
        job_b = await make_job("b", 0.01)

        await queue.enqueue("C001", "123.456", job_a)
        await queue.enqueue("C001", "123.456", job_b)
        await asyncio.sleep(0.15)

        assert order == ["a-start", "a-end", "b-start", "b-end"]

    @pytest.mark.asyncio
    async def test_jobs_for_different_sessions_run_concurrently(self):
        queue = SessionQueue()
        order = []

        async def make_job(label, delay):
            async def job():
                order.append(f"{label}-start")
                await asyncio.sleep(delay)
                order.append(f"{label}-end")

            return job

        job_a = await make_job("a", 0.05)
        job_b = await make_job("b", 0.05)

        await queue.enqueue("C001", "111.000", job_a)
        await queue.enqueue("C001", "222.000", job_b)
        await asyncio.sleep(0.15)

        assert order[0] == "a-start"
        assert order[1] == "b-start"

    @pytest.mark.asyncio
    async def test_idle_queue_cleaned_up(self):
        queue = SessionQueue()

        async def job():
            pass

        await queue.enqueue("C001", "123.456", job)
        await asyncio.sleep(0.05)

        assert ("C001", "123.456") not in queue._queues
        assert ("C001", "123.456") not in queue._consumers

    @pytest.mark.asyncio
    async def test_failed_job_does_not_block_next(self):
        queue = SessionQueue()
        executed = []

        async def failing_job():
            raise RuntimeError("boom")

        async def good_job():
            executed.append(True)

        await queue.enqueue("C001", "123.456", failing_job)
        await queue.enqueue("C001", "123.456", good_job)
        await asyncio.sleep(0.05)

        assert executed == [True]
