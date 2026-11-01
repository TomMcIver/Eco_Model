"""`eco-model` command line: ingest, backtest, tax."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from eco_model.contracts import VintageTrack

DEFAULT_DB = Path("data/eco_model.duckdb")
TRACK_CHOICES = {"real_time": (VintageTrack.REAL_TIME,),
                 "pseudo_oos": (VintageTrack.PSEUDO_OOS,),
                 "both": (VintageTrack.REAL_TIME, VintageTrack.PSEUDO_OOS)}
# Default first reference quarter per track: real-time vintages are archived from 2017.
DEFAULT_START = {VintageTrack.REAL_TIME: "2017Q1", VintageTrack.PSEUDO_OOS: "1995Q1"}


def _backtest_parser(sub) -> None:
    p = sub.add_parser("backtest", help="Run the point-in-time forecast backtest and write reports")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--track", choices=sorted(TRACK_CHOICES), default="both")
    p.add_argument("--start", help="First common reference quarter (default per track)")
    p.add_argument("--end", default=None, help="Last reference quarter (default: last released)")
    p.add_argument("--eval-start", default="2017-01-01",
                   help="Origins on/after this UTC date form the frozen evaluation interval")
    p.add_argument("--out", default="reports")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-boot", type=int, default=1000)


def _run_backtest(args) -> int:
    from eco_model.data.store import DuckDBObservationStore
    from eco_model.pipeline import BacktestConfig, run_track

    end = args.end or str(pd.Timestamp.now(tz="UTC").to_period("Q") - 1)
    eval_start = pd.Timestamp(args.eval_start, tz="UTC") if args.eval_start else None
    with DuckDBObservationStore(args.db) as store:
        for track in TRACK_CHOICES[args.track]:
            config = BacktestConfig(track=track, start=args.start or DEFAULT_START[track],
                                    end=end, eval_start=eval_start, seed=args.seed,
                                    n_boot=args.n_boot)
            out = run_track(store, config, Path(args.out))
            print(f"{track.value}: report written to {out / 'report.md'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["tax"]:
        from eco_model.tax.cli import main_tax
        return main_tax(argv[1:])
    if argv[:1] == ["ingest"]:
        from eco_model.data.ingest import main as main_ingest
        return main_ingest(argv[1:])
    parser = argparse.ArgumentParser(prog="eco-model", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Download Stats NZ releases into the store (see `ingest -h`)")
    sub.add_parser("tax", help="Static under-25 exemption calculator (see `tax -h`)")
    _backtest_parser(sub)
    args = parser.parse_args(argv)
    return _run_backtest(args)


if __name__ == "__main__":
    raise SystemExit(main())
