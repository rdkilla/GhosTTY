import time

from .state import SessionState


def wait_for_stable(state: SessionState, stable_ms: int, max_wait_ms: int) -> bool:
    start = time.time()
    while True:
        with state.lock:
            if not state.connected:
                return False
            since_change = (time.time() - state.last_change_ts) * 1000
            if since_change >= stable_ms:
                state.stable_rev = state.screen_rev
                state.last_stable_ts = time.time()
                return True
        if (time.time() - start) * 1000 >= max_wait_ms:
            return False
        time.sleep(0.05)
