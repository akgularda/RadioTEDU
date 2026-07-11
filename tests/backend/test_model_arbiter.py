from threading import Thread
from time import monotonic, sleep

import pytest


def test_model_arbiter_serializes_qwen_and_ollama():
    from backend.resources.model_arbiter import LeaseUnavailableError, ModelArbiter

    arbiter = ModelArbiter(max_queue=2)

    qwen_lease = arbiter.acquire("qwen", "radiotedu-en", timeout=0)

    assert qwen_lease.kind == "qwen"
    assert qwen_lease.owner == "radiotedu-en"
    assert qwen_lease.acquired_at < qwen_lease.deadline
    with pytest.raises(LeaseUnavailableError):
        arbiter.acquire("ollama", "radiotedu-fr", timeout=0)

    arbiter.release(qwen_lease)
    ollama_lease = arbiter.acquire("ollama", "radiotedu-fr", timeout=0)

    assert ollama_lease.kind == "ollama"


def test_model_arbiter_rejects_waiters_when_its_bounded_queue_has_no_capacity():
    from backend.resources.model_arbiter import LeaseQueueFullError, ModelArbiter

    arbiter = ModelArbiter(max_queue=0)
    arbiter.acquire("qwen", "radiotedu-en", timeout=0)

    with pytest.raises(LeaseQueueFullError):
        arbiter.acquire("ollama", "radiotedu-fr", timeout=1)


def test_model_arbiter_serves_bounded_waiters_in_arrival_order():
    from backend.resources.model_arbiter import ModelArbiter

    arbiter = ModelArbiter(max_queue=2)
    held_lease = arbiter.acquire("qwen", "radiotedu-en", timeout=0)
    owners: list[str] = []
    failures: list[Exception] = []

    def wait_for_model(kind: str, owner: str) -> None:
        try:
            lease = arbiter.acquire(kind, owner, timeout=0.5)
            owners.append(owner)
            arbiter.release(lease)
        except Exception as error:  # asserted after all threads are joined
            failures.append(error)

    first = Thread(target=wait_for_model, args=("ollama", "radiotedu-fr"))
    second = Thread(target=wait_for_model, args=("qwen", "radiotedu-en"))
    first.start()
    _wait_until(lambda: arbiter.queue_depth == 1)
    second.start()
    _wait_until(lambda: arbiter.queue_depth == 2)

    arbiter.release(held_lease)
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert owners == ["radiotedu-fr", "radiotedu-en"]


def test_model_arbiter_times_out_without_leaving_a_queued_request():
    from backend.resources.model_arbiter import LeaseTimeoutError, ModelArbiter

    arbiter = ModelArbiter(max_queue=1)
    arbiter.acquire("qwen", "radiotedu-en", timeout=0)

    with pytest.raises(LeaseTimeoutError):
        arbiter.acquire("ollama", "radiotedu-fr", timeout=0)

    assert arbiter.queue_depth == 0


def test_model_arbiter_releases_the_model_when_work_fails():
    from backend.resources.model_arbiter import ModelArbiter

    arbiter = ModelArbiter()

    def failed_model_work() -> None:
        raise RuntimeError("Qwen is unavailable")

    with pytest.raises(RuntimeError, match="Qwen is unavailable"):
        arbiter.run("qwen", "radiotedu-en", failed_model_work, timeout=0)

    assert arbiter.active_lease is None
    assert arbiter.acquire("ollama", "radiotedu-fr", timeout=0).kind == "ollama"


def test_model_arbiter_reclaims_an_expired_lease_before_granting_the_next_one():
    from backend.resources.model_arbiter import ModelArbiter

    now = [100.0]
    arbiter = ModelArbiter(lease_seconds=10, clock=lambda: now[0])
    expired_lease = arbiter.acquire("qwen", "radiotedu-en", timeout=0)
    now[0] = expired_lease.deadline

    ollama_lease = arbiter.acquire("ollama", "radiotedu-fr", timeout=0)

    assert ollama_lease.kind == "ollama"
    assert arbiter.active_lease is ollama_lease


def _wait_until(condition) -> None:
    deadline = monotonic() + 1
    while monotonic() < deadline:
        if condition():
            return
        sleep(0.01)
    assert condition()
