import time

from ghostty.session.state import SessionState
from ghostty.session.stability import wait_for_stable


def test_wait_for_stable_respects_warmup_window():
    state = SessionState(connected=True)
    now = time.time()
    state.screen_rev = 3
    state.first_change_ts = now
    state.last_change_ts = now - 1

    ok = wait_for_stable(state=state, stable_ms=1, max_wait_ms=30, stable_warmup_ms=80)

    assert ok is False


def test_wait_for_stable_returns_after_warmup_and_idle_time():
    state = SessionState(connected=True)
    now = time.time()
    state.screen_rev = 2
    state.first_change_ts = now - 0.2
    state.last_change_ts = now - 0.2

    ok = wait_for_stable(state=state, stable_ms=20, max_wait_ms=100, stable_warmup_ms=50)

    assert ok is True
    assert state.stable_rev == 2


def test_wait_for_stable_waits_at_least_stable_ms_from_call_time():
    state = SessionState(connected=True)
    now = time.time()
    state.screen_rev = 5
    state.first_change_ts = now - 5
    state.last_change_ts = now - 5

    start = time.time()
    ok = wait_for_stable(state=state, stable_ms=80, max_wait_ms=200, stable_warmup_ms=0)
    elapsed_ms = (time.time() - start) * 1000

    assert ok is True
    assert elapsed_ms >= 70
