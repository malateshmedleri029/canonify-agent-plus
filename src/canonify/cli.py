"""Canonify Agent+ command-line interface.

Examples:
    python -m canonify run data/samples/new_to_old_bad.csv --tenant acme
    python -m canonify run data/samples/new_to_old_bad.csv --mode gcp --tenant acme
    python -m canonify review --tenant acme          # list the human-review queue
    python -m canonify dict --tenant acme            # show the learned dictionary
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config, DATA_DIR
from .pipeline import run_pipeline
from .rag.dictionary import get_dictionary


def _build_config(args) -> Config:
    return Config.from_env(
        mode=getattr(args, "mode", None),
        tenant_id=getattr(args, "tenant", None),
        schema_path=Path(args.schema) if getattr(args, "schema", None) else None,
    )


def cmd_run(args) -> int:
    config = _build_config(args)
    result, paths = run_pipeline(Path(args.input), config=config)
    print(json.dumps(result.summary(), indent=2))
    print("\nArtifacts written:")
    for name, path in paths.items():
        print(f"  - {name}: {path}")
    return 0


def cmd_review(args) -> int:
    config = _build_config(args)
    queue_path = Path(config.output_dir) / config.tenant_id / "review_queue.json"
    if not queue_path.exists():
        print(f"No review queue found for tenant '{config.tenant_id}'. Run the pipeline first.")
        return 1
    print(queue_path.read_text())
    return 0


def cmd_dict(args) -> int:
    config = _build_config(args)
    dictionary = get_dictionary(config)
    print(json.dumps(dictionary.all_entries(config.tenant_id), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Shared flags usable before OR after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=["local", "gcp"],
                        help="Execution backend (default: env or local).")
    common.add_argument("--tenant", help="Tenant id for namespaced learning (default: global).")
    common.add_argument("--schema", help="Path to a canonical schema file (yaml/json).")

    p = argparse.ArgumentParser(prog="canonify", parents=[common],
                                description="Canonify Agent+ data canonicalizer.")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", parents=[common], help="Canonicalize a file.")
    r.add_argument("input", help="Path to the raw input CSV.")
    r.set_defaults(func=cmd_run)

    rv = sub.add_parser("review", parents=[common], help="Show the human-review queue.")
    rv.set_defaults(func=cmd_review)

    d = sub.add_parser("dict", parents=[common], help="Show the learned dictionary.")
    d.set_defaults(func=cmd_dict)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
