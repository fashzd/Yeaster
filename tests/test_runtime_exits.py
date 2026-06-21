"""Runtime trailing-stop tests — the live ATR trail and its safety floor."""

from __future__ import annotations

from types import SimpleNamespace

from yeaster.runtime import exits as ex
from yeaster.runtime import state as state_mod


def _pos(entry=100.0, atr_entry=5.0, peak=100.0, qty=1.0, stop=92.0, tp=140.0):
    return {"entry_price": entry, "atr_entry": atr_entry, "peak_price": peak,
            "qty": qty, "stop_price": stop, "tp_price": tp, "stop_id": None, "tp_id": None}


def test_atr_trail_distance():
    # peak 130, ATR 5, k=3 -> trail at 130 - 15 = 115 (above the 92 hard stop).
    assert abs(ex._trail_stop(_pos(), peak=130.0) - 115.0) < 1e-6


def test_trail_floored_by_hard_stop():
    # No rise yet: ATR trail (100-15=85) sits below the 92 hard stop -> floored to 92.
    assert abs(ex._trail_stop(_pos(peak=100.0), peak=100.0) - 92.0) < 1e-6


def test_fixed_fallback_when_no_atr():
    # atr_entry 0 -> fixed-% fallback (3%): peak 130 -> 126.1, above hard stop.
    assert abs(ex._trail_stop(_pos(atr_entry=0.0), peak=130.0) - 126.1) < 1e-6


def test_trail_never_below_hard_stop_across_peaks():
    hard = 100.0 * (1.0 - 0.08)
    for peak in (100.0, 105.0, 120.0, 200.0):
        assert ex._trail_stop(_pos(peak=peak), peak=peak) >= hard - 1e-9


def test_reconcile_trails_with_atr_paper():
    # One open position making a new high (below TP, above stop) should ratchet the
    # stop up to peak - 3*ATR via the live reconcile path (paper backend, offline).
    st = {"positions": {"CAKE": _pos(entry=100.0, atr_entry=5.0, peak=100.0, stop=92.0, tp=140.0)}}
    by_sym = {"CAKE": SimpleNamespace(price_usd=130.0)}
    actions = ex.reconcile(st, broker=None, by_sym=by_sym, mandate=None, twak_backend="paper")
    trail = [a for a in actions if a["action"] == "trail"]
    assert trail and abs(trail[0]["new_stop"] - 115.0) < 1e-6
    assert st["positions"]["CAKE"]["stop_price"] == trail[0]["new_stop"]


def test_record_entry_persists_atr():
    state = {"positions": {}, "trades_today": 0}
    state_mod.record_entry(state, "CAKE", 100.0, 1.0, 92.0, 140.0, None, None, atr_entry=7.5)
    assert state["positions"]["CAKE"]["atr_entry"] == 7.5
