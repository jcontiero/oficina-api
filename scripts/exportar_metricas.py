"""Publica snapshots reais de OS e saúde no DogStatsD, sem chave Datadog."""

import json
import os
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from sqlalchemy import create_engine, text

DURACOES_SQL = """
WITH etapas AS (
  SELECT status_novo::text AS status, ocorrido_em,
         LEAD(ocorrido_em) OVER (
           PARTITION BY os_id ORDER BY sequencia, ocorrido_em, id
         ) AS saida
  FROM historico_os
)
SELECT status, AVG(EXTRACT(EPOCH FROM (saida - ocorrido_em))) AS segundos,
       COUNT(*) AS amostras
FROM etapas
WHERE saida IS NOT NULL AND saida >= :inicio AND saida >= ocorrido_em
GROUP BY status
"""


def metric_line(name, value, tags):
    return f"{name}:{float(value)}|g|#{','.join(tags)}"


def snapshot(connection, agora):
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    created = connection.execute(
        text("SELECT COUNT(*) FROM ordens_de_servico WHERE criada_em >= :inicio"),
        {"inicio": hoje},
    ).scalar_one()
    values = [("oficina.os.criadas_dia", created, [])]
    # A abertura v1 inicia a etapa DIAGNOSTICO na Saga enquanto a OS fica RECEBIDA.
    # Mede o intervalo persistido até a primeira resposta, sem inferir um status ausente.
    diagnosis = (
        connection.execute(
            text(
                "SELECT AVG(EXTRACT(EPOCH FROM (i.recebido_em - s.criada_em))) AS segundos, "
                "COUNT(*) AS amostras FROM saga_instances s "
                "JOIN (SELECT saga_id, MIN(recebido_em) AS recebido_em FROM inbox_eventos "
                "WHERE event_type = 'DiagnosticoConcluido.v1' GROUP BY saga_id) i "
                "ON i.saga_id = s.id "
                "WHERE i.recebido_em >= :inicio AND i.recebido_em >= s.criada_em"
            ),
            {"inicio": agora - timedelta(hours=24)},
        )
        .mappings()
        .one()
    )
    if diagnosis["amostras"]:
        values += [
            ("oficina.saga.tempo_diagnostico_segundos", diagnosis["segundos"], []),
            ("oficina.saga.amostras_diagnostico", diagnosis["amostras"], []),
        ]
    for row in connection.execute(
        text(DURACOES_SQL), {"inicio": agora - timedelta(hours=24)}
    ).mappings():
        values.append(
            (
                "oficina.os.tempo_status_segundos",
                row["segundos"],
                [f"status:{row['status'].lower()}"],
            )
        )
        values.append(
            (
                "oficina.os.amostras_status",
                row["amostras"],
                [f"status:{row['status'].lower()}"],
            )
        )
    for status, metric in (
        ("PENDENTE", "oficina.outbox.pendentes"),
        ("FALHA_AGENDADA", "oficina.outbox.falhas_agendadas"),
    ):
        count = connection.execute(
            text("SELECT COUNT(*) FROM outbox_eventos WHERE status = :status"),
            {"status": status},
        ).scalar_one()
        values.append((metric, count, []))
    manual = connection.execute(
        text("SELECT COUNT(*) FROM saga_instances WHERE estado = 'INTERVENCAO_MANUAL'")
    ).scalar_one()
    financial = connection.execute(
        text(
            "SELECT COUNT(*) FROM saga_instances "
            "WHERE compensacao_financeira_status = 'FALHA_PENDENTE'"
        )
    ).scalar_one()
    values += [
        ("oficina.saga.intervencao_manual", manual, []),
        ("oficina.saga.falha_financeira_pendente", financial, []),
    ]
    return values


def healthcheck(url):
    start = time.monotonic()
    try:
        with urlopen(url, timeout=4) as response:  # noqa: S310
            ready = int(response.status == 200)
    except (HTTPError, URLError, TimeoutError, OSError):
        ready = 0
    return ready, time.monotonic() - start


def main():
    env = os.getenv("ENVIRONMENT", "homolog")
    if env != "homolog":
        raise ValueError("Este coletor está configurado somente para homologação")
    database_url = (
        os.getenv("DATABASE_URL")
        or Path(os.getenv("DATABASE_URL_FILE", "/mnt/secrets-store/DATABASE_URL"))
        .read_text()
        .strip()
    )
    host = os.getenv("DD_DOGSTATSD_HOST", "datadog.datadog.svc.cluster.local")
    engine = create_engine(database_url, connect_args={"timeout": 15})
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            metrics = snapshot(connection, datetime.now(timezone.utc))
    finally:
        engine.dispose()
    common = [f"env:{env}", "service:oficina-api", "kube_namespace:oficina-homolog"]
    lines = [metric_line(name, value, common + tags) for name, value, tags in metrics]
    for service in ["oficina-api", "oficina-billing", "oficina-execucao"]:
        url = f"http://{service}-service.oficina-homolog.svc.cluster.local/health/ready"
        ready, latency = healthcheck(url)
        tags = [f"env:{env}", f"service:{service}", "kube_namespace:oficina-homolog"]
        lines += [
            metric_line("oficina.health.ready", ready, tags),
            metric_line("oficina.health.latencia_segundos", latency, tags),
        ]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        for line in lines:
            client.sendto(line.encode(), (host, 8125))
    print(
        json.dumps(
            {
                "event": "observabilidade_snapshot_enviado",
                "env": env,
                "metricas": len(lines),
                "fonte": "historico_os_e_healthchecks",
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "event": "observabilidade_snapshot_falhou",
                    "level": "ERROR",
                    "error_type": type(exc).__name__,
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
