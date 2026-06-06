"""The memoizing single-flight recorder must not deadlock when the upstream call fails, and
must honor an atomic cost cap."""
import threading

import pytest

from core.types import ModelError
from evals.run_gauntlet import RecordingClient


class _Boom:
    def complete(self, *, model, system, messages, max_tokens):
        raise ModelError("upstream down")


def test_owner_failure_releases_waiters_no_deadlock():
    rec = RecordingClient(_Boom())
    errors = []

    def call():
        try:
            rec.complete(model="m", system="s", messages=[{"role": "user", "content": "x"}],
                         max_tokens=10)
        except Exception as e:  # noqa: BLE001
            errors.append(type(e).__name__)

    threads = [threading.Thread(target=call) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert all(not t.is_alive() for t in threads), "a thread deadlocked on ev.wait()"
    assert len(errors) == 5  # every caller saw a clean error, none hung


def test_cost_cap_raises_once_exceeded():
    from core.types import ModelResponse

    class _Pricey:
        def complete(self, *, model, system, messages, max_tokens):
            return ModelResponse(text="ok", model="deepseek-chat", input_tokens=1000,
                                 output_tokens=1000, cost_usd=0.50, latency_ms=1.0)

    rec = RecordingClient(_Pricey(), max_usd=0.40)
    # first unique call is allowed (cost checked before the call; starts at 0)
    rec.complete(model="m", system="s", messages=[{"role": "user", "content": "a"}], max_tokens=10)
    assert rec.total_cost == 0.50
    # next unique call is refused because the cap is now exceeded
    with pytest.raises(RuntimeError):
        rec.complete(model="m", system="s", messages=[{"role": "user", "content": "b"}],
                     max_tokens=10)
