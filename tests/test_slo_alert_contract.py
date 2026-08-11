from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(relative_path: str) -> dict:
    return yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def test_slo_objectives_match_dashboard_thresholds() -> None:
    slo = load_yaml("config/slo.yaml")
    dashboard = load_yaml("config/dashboard.yaml")
    panels = {panel["id"]: panel for panel in dashboard["dashboard"]["panels"]}

    expected_mapping = {
        "latency_p95_ms": "latency",
        "error_rate_pct": "errors",
        "cost_usd_60m": "cost",
        "tokens_total_60m": "tokens",
        "quality_score_avg": "quality",
    }

    assert slo["window"] == "28d"
    assert set(expected_mapping) <= slo["slis"].keys()
    for sli_name, panel_id in expected_mapping.items():
        assert (
            slo["slis"][sli_name]["objective"]
            == panels[panel_id]["threshold"]["value"]
        )


def test_alerts_are_symptom_based_and_have_valid_runbooks() -> None:
    alerts = load_yaml("config/alert_rules.yaml")["alerts"]

    assert {alert["name"] for alert in alerts} == {
        "HighUserLatency",
        "HighRequestErrorRate",
        "CostBudgetAtRisk",
    }
    for alert in alerts:
        assert alert["type"] == "symptom-based"
        assert alert["owner"] == "sre-alerts (ChiQuang - Người 4)"
        runbook_path = alert["runbook"].split("#", 1)[0]
        assert (REPO_ROOT / runbook_path).is_file()


def test_alert_conditions_keep_the_approved_thresholds_and_durations() -> None:
    alerts = {
        alert["name"]: alert
        for alert in load_yaml("config/alert_rules.yaml")["alerts"]
    }

    assert alerts["HighUserLatency"]["condition"] == "latency_p95_ms > 2000 for 5m"
    assert alerts["HighRequestErrorRate"]["condition"] == "error_rate_pct > 2 for 5m"
    assert alerts["CostBudgetAtRisk"]["condition"] == "cost_usd_60m > 2.5 for 5m"
