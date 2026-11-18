"""Cria ou atualiza o dashboard e os alertas de homologação sem duplicá-los."""

import argparse
import json
import os
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1] / "monitoring" / "datadog"


def credential(variable, secret, project):
    value = os.getenv(variable)
    if value:
        return value
    return subprocess.check_output(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=" + secret,
            "--project=" + project,
        ],
        text=True,
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--project", default="fiap-project-514922")
    args = parser.parse_args()
    dashboard = json.loads((ROOT / "dashboard.json").read_text())
    monitors = json.loads((ROOT / "monitors.json").read_text())
    if not args.apply:
        print(
            json.dumps(
                {
                    "dashboard": dashboard["title"],
                    "widgets": len(dashboard["widgets"]),
                    "monitores": len(monitors),
                    "aplicar": False,
                },
                ensure_ascii=False,
            )
        )
        return
    headers = {
        "DD-API-KEY": credential(
            "DD_API_KEY", "export-logs-to-datadog-api-key", args.project
        ),
        "DD-APPLICATION-KEY": credential(
            "DD_APP_KEY", "oficina-datadog-application-key", args.project
        ),
    }
    with httpx.Client(
        base_url="https://api.datadoghq.com", headers=headers, timeout=30
    ) as client:

        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if not response.is_success:
                raise RuntimeError(
                    f"Datadog {path}: HTTP {response.status_code}: {response.text[:1500]}"
                )
            return response.json()

        # O Datadog valida consultas/opções antes da criação dos monitores.
        for monitor in monitors:
            call("POST", "/api/v1/monitor/validate", json=monitor)
        existing = call("GET", "/api/v1/dashboard").get("dashboards", [])
        found = next((d for d in existing if d["title"] == dashboard["title"]), None)
        created = (
            call("PUT", "/api/v1/dashboard/" + found["id"], json=dashboard)
            if found
            else call("POST", "/api/v1/dashboard", json=dashboard)
        )
        known = call("GET", "/api/v1/monitor")
        results = []
        for monitor in monitors:
            found = next(
                (
                    m
                    for m in known
                    if m["name"] == monitor["name"]
                    and "managed_by:oficina" in m.get("tags", [])
                ),
                None,
            )
            result = (
                call("PUT", f"/api/v1/monitor/{found['id']}", json=monitor)
                if found
                else call("POST", "/api/v1/monitor", json=monitor)
            )
            results.append({"id": result["id"], "nome": result["name"]})
        url = "https://app.datadoghq.com" + created["url"]
        print(
            json.dumps(
                {
                    "dashboard_id": created["id"],
                    "dashboard_url": url,
                    "monitores": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
