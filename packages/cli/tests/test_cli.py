import json

from fathomark_cli.cli import main


class FakeClient:
    def health(self):
        return {"status": "ok"}

    def create_run(self, payload, idem_key):
        return {"state": "created", "payload": payload, "idempotency_key": idem_key}

    def close(self):
        pass


def test_health_command_prints_json(capsys):
    assert main(["health"], client_factory=lambda _: FakeClient()) == 0

    assert json.loads(capsys.readouterr().out) == {"status": "ok"}


def test_run_create_command_passes_explicit_scope_and_idempotency(capsys):
    assert (
        main(
            [
                "run",
                "create",
                "--symbol",
                "ADBE",
                "--exchange",
                "NASDAQ",
                "--research-role",
                "core",
                "--horizon",
                "5-10y",
                "--research-date",
                "2026-09-03",
                "--data-cutoff",
                "2026-09-03",
                "--framework-ref",
                "common-stock@1.0.0",
                "--idempotency-key",
                "cli-create",
            ],
            client_factory=lambda _: FakeClient(),
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)["payload"]
    assert payload["symbol"] == "ADBE"
    assert payload["framework_ref"] == "common-stock@1.0.0"


def test_plugin_auth_reports_configuration_without_printing_secret(monkeypatch, capsys):
    monkeypatch.setenv("EXAMPLE_API_KEY", "do-not-print-me")

    assert (
        main(
            [
                "plugin",
                "auth",
                "--provider",
                "example",
                "--env-var",
                "EXAMPLE_API_KEY",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    body = json.loads(output)
    assert body["configured"] is True
    assert "do-not-print-me" not in output


def test_plugin_contract_template_is_copyable_text(capsys):
    assert main(["plugin", "contract-template", "--kind", "data"]) == 0

    output = capsys.readouterr().out
    assert "class ExampleDataProvider" in output
    assert "contract" in output.lower()
