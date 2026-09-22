"""Small, explicit CLI for the Fathomark API and plugin contracts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

from fathomark_sdk import FathomarkAPIError, FathomarkClient

_DATA_PROVIDER_TEMPLATE = '''"""Example DataProvider contract template.

The host validates returned evidence before it reaches the core database.
Credentials are read from the environment and never returned by the plugin.
"""


class ExampleDataProvider:
    """Contract template: replace the example methods with real code."""

    name = "example"
    version = "0.1.0"
    auth_env = "EXAMPLE_API_KEY"

    def health(self) -> dict[str, str]:
        """Return a safe status payload without exposing credentials."""
        return {"provider": self.name, "status": "not_configured"}

    def fetch(self, scope: dict) -> list[dict]:
        """Return validated EvidenceItem-shaped dictionaries for ``scope``."""
        raise NotImplementedError
'''

_LLM_PROVIDER_TEMPLATE = '''"""Example LLMProvider contract template."""


class ExampleLLMProvider:
    name = "example"
    version = "0.1.0"
    auth_env = "EXAMPLE_API_KEY"

    def complete(self, request):
        """Return a validated structured response; never decide final scores."""
        raise NotImplementedError
'''

_THEME_TEMPLATE = '''"""Example ReportTheme contract template."""


class ExampleReportTheme:
    name = "example"
    version = "0.1.0"

    def render(self, report_model):
        """Render from ReportModel only; do not recalculate scores."""
        raise NotImplementedError
'''


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fathomark")
    parser.add_argument(
        "--base-url",
        default=os.getenv("FATHOMARK_API_URL", "http://localhost:8000"),
        help="Fathomark API base URL (default: FATHOMARK_API_URL or localhost)",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("health", help="check API process health")

    run = commands.add_parser("run", help="create, execute, inspect or approve a run")
    run_commands = run.add_subparsers(dest="run_command", required=True)

    create = run_commands.add_parser("create", help="create a research run")
    create.add_argument("--symbol", required=True)
    create.add_argument("--exchange", required=True)
    create.add_argument(
        "--research-role", required=True, choices=("core", "offensive", "tactical")
    )
    create.add_argument("--horizon", required=True)
    create.add_argument("--research-date", required=True)
    create.add_argument("--data-cutoff", required=True)
    create.add_argument("--framework-ref", required=True)
    create.add_argument("--idempotency-key", required=True)

    for name, help_text in (
        ("show", "show run state"),
        ("execute", "execute the configured orchestrator"),
        ("result", "show the draft or approved result"),
    ):
        command = run_commands.add_parser(name, help=help_text)
        command.add_argument("run_id")

    approve = run_commands.add_parser("approve", help="approve a draft run")
    approve.add_argument("run_id")
    approve.add_argument("--lock-version", type=int)
    approve.add_argument("--idempotency-key", required=True)
    approve.add_argument("--actor", default="cli")

    plugin = commands.add_parser(
        "plugin", help="inspect plugin authentication/contracts"
    )
    plugin_commands = plugin.add_subparsers(dest="plugin_command", required=True)
    auth = plugin_commands.add_parser(
        "auth", help="check an environment-backed plugin credential"
    )
    auth.add_argument("--provider", required=True)
    auth.add_argument("--env-var", required=True)
    template = plugin_commands.add_parser(
        "contract-template", help="print a provider/theme contract template"
    )
    template.add_argument("--kind", choices=("data", "llm", "theme"), required=True)
    return parser


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def _plugin_command(args: argparse.Namespace) -> int:
    if args.plugin_command == "auth":
        _print_json(
            {
                "provider": args.provider,
                "credential_env": args.env_var,
                "credential_source": "environment",
                "configured": bool(os.getenv(args.env_var)),
                "secret_printed": False,
            }
        )
        return 0

    templates = {
        "data": _DATA_PROVIDER_TEMPLATE,
        "llm": _LLM_PROVIDER_TEMPLATE,
        "theme": _THEME_TEMPLATE,
    }
    print(templates[args.kind], end="")
    return 0


def _run_command(args: argparse.Namespace, client: Any) -> int:
    if args.run_command == "create":
        payload = {
            "symbol": args.symbol,
            "exchange": args.exchange,
            "research_role": args.research_role,
            "horizon": args.horizon,
            "research_date": args.research_date,
            "data_cutoff": args.data_cutoff,
            "framework_ref": args.framework_ref,
        }
        _print_json(client.create_run(payload, idem_key=args.idempotency_key))
    elif args.run_command == "show":
        _print_json(client.get_run(args.run_id))
    elif args.run_command == "execute":
        _print_json(client.execute(args.run_id))
    elif args.run_command == "result":
        _print_json(client.get_result(args.run_id))
    else:
        lock_version = args.lock_version
        if lock_version is None:
            lock_version = client.get_run(args.run_id)["lock_version"]
        _print_json(
            client.approve(
                args.run_id,
                expected_lock_version=lock_version,
                idem_key=args.idempotency_key,
                actor=args.actor,
            )
        )
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[str], Any] | None = None,
) -> int:
    """Run the CLI and return a process-style exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "plugin":
        return _plugin_command(args)
    if args.command is None:
        build_parser().print_help()
        return 2

    factory = client_factory or FathomarkClient
    client = factory(args.base_url)
    try:
        if args.command == "health":
            _print_json(client.health())
            return 0
        return _run_command(args, client)
    except FathomarkAPIError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover - exercised by the console script
    raise SystemExit(main())
