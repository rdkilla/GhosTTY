import time

from .state import SessionState


def wait_for_stable(
    state: SessionState,
    stable_ms: int,
    max_wait_ms: int,
    stable_warmup_ms: int = 0,
) -> bool:
    start = time.time()
    while True:
        with state.lock:
            if not state.connected:
                return False
            now = time.time()
            wait_anchor = max(state.last_change_ts, start)
            since_change = (now - state.last_change_ts) * 1000
            since_anchor = (now - wait_anchor) * 1000
            if state.screen_rev == 0:
                if since_change >= stable_ms and since_anchor >= stable_ms:
                    state.stable_rev = state.screen_rev
                    state.last_stable_ts = now
                    return True
            else:
                stream_age_ms = (now - state.first_change_ts) * 1000 if state.first_change_ts > 0 else 0
                if stream_age_ms >= stable_warmup_ms and since_change >= stable_ms and since_anchor >= stable_ms:
                    state.stable_rev = state.screen_rev
                    state.last_stable_ts = now
                    return True
        if (time.time() - start) * 1000 >= max_wait_ms:
            return False
        time.sleep(0.05)
