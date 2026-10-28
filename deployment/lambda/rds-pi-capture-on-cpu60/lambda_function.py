import gzip
import io
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import boto3

pi = boto3.client("pi")
rds = boto3.client("rds")
s3 = boto3.client("s3")
sns = boto3.client("sns")
cw = boto3.client("cloudwatch")
ecs = boto3.client("ecs")
logs = boto3.client("logs")

BUCKET = os.environ["CAPTURE_BUCKET"]
PREFIX = os.environ.get("CAPTURE_PREFIX", "rds-pi-captures")
SNS_TOPIC = os.environ.get("SNS_TOPIC_ARN", "")
INSTANCES = [x.strip() for x in os.environ.get("DB_INSTANCES", "prod,prod-replica").split(",") if x.strip()]
LOOKBACK_MIN = int(os.environ.get("LOOKBACK_MINUTES", "30"))
TOP_N = int(os.environ.get("TOP_N", "10"))

ECS_CLUSTER = os.environ.get("ECS_CLUSTER", "fastapi-prod-cluster")
ECS_SERVICE = os.environ.get("ECS_SERVICE", "backend-core-prod-service")
OTHER_SERVICES = [
    s.strip()
    for s in os.environ.get(
        "ECS_OTHER_SERVICES",
        "integracion-fintegro-prod-service,giro-automatico-prod-service,lsf-equifax-prod-service",
    ).split(",")
    if s.strip()
]
ALB_LOG_BUCKET = os.environ.get("ALB_LOG_BUCKET", "logros-alb-access-logs-870376008575")
ALB_LOG_PREFIX = os.environ.get(
    "ALB_LOG_PREFIX",
    "alb/AWSLogs/870376008575/elasticloadbalancing/us-east-1",
)
ALB_FULL_NAME = os.environ.get("ALB_FULL_NAME", "app/fastapi-prod-alb/a2f928f9004d2ccd")
TG_FULL_NAME = os.environ.get("TG_FULL_NAME", "targetgroup/backend-core-prod-tg/0cd48f95a77e0119")
TG_MARKER = os.environ.get("TG_MARKER", "backend-core-prod-tg")
APP_LOG_GROUP = os.environ.get("APP_LOG_GROUP", "/ecs/backend-core-prod")
BACKEND_LOOKBACK_MIN = int(os.environ.get("BACKEND_LOOKBACK_MINUTES", "15"))
SLOW_SECONDS = float(os.environ.get("SLOW_REQUEST_SECONDS", "2"))
CL = timezone(timedelta(hours=-4))


def _cl(dt):
    if dt is None:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CL).strftime("%Y-%m-%d %H:%M:%S")


def _resource_id(db_id: str) -> str:
    resp = rds.describe_db_instances(DBInstanceIdentifier=db_id)
    return resp["DBInstances"][0]["DbiResourceId"]


def _cpu_snapshot(db_id: str, start, end):
    resp = cw.get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Maximum", "Average"],
    )
    points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
    if not points:
        return None
    last = points[-1]
    peak = max(points, key=lambda p: p["Maximum"])
    return {
        "latest_max": round(last["Maximum"], 2),
        "latest_avg": round(last["Average"], 2),
        "window_peak_max": round(peak["Maximum"], 2),
        "window_peak_at": peak["Timestamp"].astimezone(timezone.utc).isoformat(),
        "series": [
            {
                "at": p["Timestamp"].astimezone(timezone.utc).isoformat(),
                "max": round(p["Maximum"], 2),
                "avg": round(p["Average"], 2),
            }
            for p in points
        ],
    }


def _dim_keys(resource_id: str, start, end, group: str, limit=None):
    try:
        resp = pi.describe_dimension_keys(
            ServiceType="RDS",
            Identifier=resource_id,
            StartTime=start,
            EndTime=end,
            Metric="db.load.avg",
            GroupBy={"Group": group},
            MaxResults=limit or TOP_N,
        )
    except Exception as e:
        return [{"error": str(e)}]
    out = []
    for item in resp.get("Keys", []):
        out.append({"total_load": item.get("Total"), "dimensions": item.get("Dimensions") or {}})
    return out


def capture_instance(db_id: str, end=None, lookback_min=None):
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(minutes=lookback_min or LOOKBACK_MIN)
    rid = _resource_id(db_id)
    return {
        "db_instance": db_id,
        "dbi_resource_id": rid,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "cpu": _cpu_snapshot(db_id, start, end),
        "top_sql": _dim_keys(rid, start, end, "db.sql"),
        "top_waits": _dim_keys(rid, start, end, "db.wait_event"),
        "top_wait_types": _dim_keys(rid, start, end, "db.wait_event_type"),
        "top_users": _dim_keys(rid, start, end, "db.user"),
        "top_dbs": _dim_keys(rid, start, end, "db"),
    }


def _metric_series(namespace, metric, dimensions, start, end, stat="Average"):
    resp = cw.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=[stat],
    )
    points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
    return [{"at": p["Timestamp"].astimezone(timezone.utc).isoformat(), "value": round(p[stat], 2)} for p in points]


def _series_summary(points):
    if not points:
        return None
    peak = max(points, key=lambda p: p["value"])
    return {
        "latest": points[-1]["value"],
        "latest_at": points[-1]["at"],
        "peak": peak["value"],
        "peak_at": peak["at"],
        "hot_minutes": [p for p in points if p["value"] >= 40],
    }


def _ecs_service_metrics(service, start, end):
    dims = [
        {"Name": "ClusterName", "Value": ECS_CLUSTER},
        {"Name": "ServiceName", "Value": service},
    ]
    cpu = _metric_series("AWS/ECS", "CPUUtilization", dims, start, end)
    mem = _metric_series("AWS/ECS", "MemoryUtilization", dims, start, end)
    return {"service": service, "cpu": _series_summary(cpu), "memory": _series_summary(mem)}


def _service_snapshot():
    desc = ecs.describe_services(cluster=ECS_CLUSTER, services=[ECS_SERVICE])["services"][0]
    arns = ecs.list_tasks(cluster=ECS_CLUSTER, serviceName=ECS_SERVICE, desiredStatus="RUNNING").get("taskArns") or []
    tasks = ecs.describe_tasks(cluster=ECS_CLUSTER, tasks=arns)["tasks"] if arns else []
    td = ecs.describe_task_definition(taskDefinition=desc["taskDefinition"])["taskDefinition"]
    image = ""
    for c in td.get("containerDefinitions") or []:
        if c.get("name") == "app" or not image:
            image = c.get("image") or ""
    task_rows = []
    for t in tasks:
        ips = []
        for att in t.get("attachments") or []:
            for kv in att.get("details") or []:
                if kv.get("name") == "privateIPv4Address":
                    ips.append(kv.get("value"))
        task_rows.append(
            {
                "task_arn": t.get("taskArn", "").split("/")[-1],
                "last_status": t.get("lastStatus"),
                "started_at": t.get("startedAt").isoformat() if t.get("startedAt") else None,
                "cpu": t.get("cpu"),
                "memory": t.get("memory"),
                "ips": ips,
            }
        )
    return {
        "desired": desc.get("desiredCount"),
        "running": desc.get("runningCount"),
        "status": desc.get("status"),
        "task_definition": desc.get("taskDefinition", "").split("/")[-1],
        "image": image,
        "task_cpu": td.get("cpu"),
        "task_memory": td.get("memory"),
        "tasks": task_rows,
    }


def _alb_metric_block(start, end):
    dims = [
        {"Name": "LoadBalancer", "Value": ALB_FULL_NAME},
        {"Name": "TargetGroup", "Value": TG_FULL_NAME},
    ]
    out = {}
    for metric in ("RequestCount", "HTTPCode_Target_2XX_Count", "HTTPCode_Target_4XX_Count", "HTTPCode_Target_5XX_Count"):
        pts = _metric_series("AWS/ApplicationELB", metric, dims, start, end, stat="Sum")
        out[metric] = round(sum(p["value"] for p in pts), 0)
    try:
        resp = cw.get_metric_statistics(
            Namespace="AWS/ApplicationELB",
            MetricName="TargetResponseTime",
            Dimensions=dims,
            StartTime=start,
            EndTime=end,
            Period=60,
            ExtendedStatistics=["p50", "p90", "p99"],
        )
        points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
        if points:
            last = points[-1]
            ext = last.get("ExtendedStatistics") or {}
            out["latency_latest_at"] = last["Timestamp"].astimezone(timezone.utc).isoformat()
            out["p50"] = round(ext.get("p50", 0), 3)
            out["p90"] = round(ext.get("p90", 0), 3)
            out["p99"] = round(ext.get("p99", 0), 3)
            worst = max(points, key=lambda p: (p.get("ExtendedStatistics") or {}).get("p99", 0))
            out["p99_peak"] = round((worst.get("ExtendedStatistics") or {}).get("p99", 0), 3)
            out["p99_peak_at"] = worst["Timestamp"].astimezone(timezone.utc).isoformat()
    except Exception as e:
        out["latency_error"] = str(e)
    return out


def _split_alb(line):
    parts = []
    cur = []
    quoted = False
    for ch in line.rstrip("\n"):
        if ch == '"':
            quoted = not quoted
            cur.append(ch)
        elif ch == " " and not quoted:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _norm_path(path):
    path = re.sub(r"/\d+", "/{id}", path or "")
    path = re.sub(r"/[0-9a-fA-F]{8,}", "/{id}", path)
    return path


def _alb_keys(now):
    end = now.replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 5)
    slots = []
    t = end
    while t >= end - timedelta(minutes=25):
        slots.append(t)
        t -= timedelta(minutes=5)
    keys = []
    newest = None
    for day in sorted({s.date() for s in slots}):
        prefix = f"{ALB_LOG_PREFIX}/{day.strftime('%Y/%m/%d')}/"
        token = None
        want = {s.strftime("%Y%m%dT%H%MZ") for s in slots if s.date() == day}
        while True:
            kw = {"Bucket": ALB_LOG_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                kw["ContinuationToken"] = token
            resp = s3.list_objects_v2(**kw)
            for obj in resp.get("Contents") or []:
                key = obj["Key"]
                if "fastapi-prod-alb" not in key:
                    continue
                if not any(tok in key for tok in want):
                    continue
                keys.append(key)
                modified = obj["LastModified"]
                if newest is None or modified > newest:
                    newest = modified
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
    return keys, newest


def _parse_alb_requests(now):
    keys, newest = _alb_keys(now)
    rows = []
    errors = []
    for key in keys:
        try:
            body = s3.get_object(Bucket=ALB_LOG_BUCKET, Key=key)["Body"].read()
        except Exception as e:
            errors.append(f"{key}: {e}")
            continue
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
            for raw in gz.read().decode("utf-8", errors="replace").splitlines():
                parts = _split_alb(raw)
                if len(parts) < 17:
                    continue
                if TG_MARKER not in parts[16]:
                    continue
                try:
                    tgt = float(parts[6])
                except ValueError:
                    continue
                try:
                    finished = datetime.strptime(parts[1][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                started = finished - timedelta(seconds=max(tgt, 0))
                req = parts[12].strip('"')
                bits = req.split(" ")
                method = bits[0] if bits else ""
                url = bits[1] if len(bits) > 1 else req
                parsed = urlparse(url)
                try:
                    sent = int(parts[11])
                except ValueError:
                    sent = 0
                rows.append(
                    {
                        "started": started,
                        "finished": finished,
                        "seconds": round(tgt, 2),
                        "elb_status": parts[8],
                        "target_status": parts[9],
                        "method": method,
                        "path": parsed.path or url,
                        "query": parsed.query[:400],
                        "bytes": sent,
                        "client": parts[3].split(":")[0],
                        "target": parts[4],
                    }
                )
    cutoff = now - timedelta(minutes=25)
    rows = [r for r in rows if r["finished"] >= cutoff]
    return {"rows": rows, "files": len(keys), "newest_file_at": newest.isoformat() if newest else None, "errors": errors[:5]}


def _app_logs(now):
    start_ms = int((now - timedelta(minutes=10)).timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    events = []
    token = None
    try:
        while len(events) < 400:
            kw = {
                "logGroupName": APP_LOG_GROUP,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 200,
            }
            if token:
                kw["nextToken"] = token
            resp = logs.filter_log_events(**kw)
            events.extend(resp.get("events") or [])
            token = resp.get("nextToken")
            if not token:
                break
    except Exception as e:
        return {"error": str(e), "events": []}
    return {"events": events[:400], "error": None}


def collect_backend(now=None, focus_at=None):
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(minutes=BACKEND_LOOKBACK_MIN)
    report = {"window_start": start.isoformat(), "window_end": now.isoformat(), "errors": []}
    try:
        report["service"] = _service_snapshot()
    except Exception as e:
        report["errors"].append(f"ecs: {e}")
        report["service"] = None
    try:
        report["backend_metrics"] = _ecs_service_metrics(ECS_SERVICE, start, now)
        report["other_services"] = [_ecs_service_metrics(name, now - timedelta(minutes=5), now) for name in OTHER_SERVICES]
    except Exception as e:
        report["errors"].append(f"metrics: {e}")
    try:
        report["alb_metrics"] = _alb_metric_block(start, now)
    except Exception as e:
        report["errors"].append(f"alb-metrics: {e}")
        report["alb_metrics"] = None
    try:
        report["alb_logs"] = _parse_alb_requests(now)
    except Exception as e:
        report["errors"].append(f"alb-logs: {e}")
        report["alb_logs"] = {"rows": [], "files": 0, "errors": [str(e)]}
    try:
        report["app_logs"] = _app_logs(now)
    except Exception as e:
        report["errors"].append(f"app-logs: {e}")
        report["app_logs"] = {"events": [], "error": str(e)}

    focus = None
    if focus_at is not None:
        if focus_at.tzinfo is None:
            focus_at = focus_at.replace(tzinfo=timezone.utc)
        focus = focus_at.astimezone(timezone.utc).replace(second=0, microsecond=0)
    else:
        cpu = (report.get("backend_metrics") or {}).get("cpu") or {}
        if cpu.get("peak", 0) >= 50 and cpu.get("peak_at"):
            focus = datetime.fromisoformat(cpu["peak_at"])
    report["focus_at"] = focus.isoformat() if focus else None
    return report


def _overlaps(row, focus):
    if focus is None:
        return False
    window_start = focus - timedelta(minutes=1)
    window_end = focus + timedelta(minutes=2)
    return row["started"] <= window_end and row["finished"] >= window_start


def _format_request(row):
    qs = f"?{row['query']}" if row["query"] else ""
    kb = row["bytes"] / 1024
    return (
        f"  {_cl(row['started'])[11:]} → {_cl(row['finished'])[11:]}  {row['seconds']:7.1f}s  "
        f"HTTP {row['target_status']}  {kb:8.1f} KB  {row['client']}  "
        f"{row['method']} {row['path']}{qs}"
    )


def _format_backend(report, heading):
    lines = [heading, ""]
    if report.get("errors"):
        lines.append("Avisos al armar el detalle:")
        for err in report["errors"]:
            lines.append(f"  - {err}")
        lines.append("")
    svc = report.get("service") or {}
    lines.append(f"Servicio: {ECS_SERVICE}  cluster: {ECS_CLUSTER}")
    if svc:
        lines.append(
            f"Tasks: {svc.get('running')}/{svc.get('desired')} {svc.get('status')}  "
            f"definición: {svc.get('task_definition')}  cpu/ram de la task: {svc.get('task_cpu')}/{svc.get('task_memory')}"
        )
        image = svc.get("image") or ""
        lines.append(f"Imagen: {image}")
        for t in svc.get("tasks") or []:
            lines.append(
                f"Task {t['task_arn']}  estado {t['last_status']}  IP {','.join(t.get('ips') or [])}  "
                f"arrancó {_cl(t.get('started_at'))} hora local"
            )
    lines.append("Hora local = UTC-4.")
    lines.append("")

    bm = report.get("backend_metrics") or {}
    for label, block in (("CPU", bm.get("cpu")), ("RAM", bm.get("memory"))):
        if not block:
            lines.append(f"{label}: sin datapoints")
            continue
        lines.append(
            f"{label}: ahora {block['latest']}% ({_cl(block['latest_at'])[11:]})  "
            f"pico {BACKEND_LOOKBACK_MIN} min {block['peak']}% a las {_cl(block['peak_at'])[11:]}"
        )
        hot = [p for p in (block.get("hot_minutes") or []) if p["value"] >= 60]
        if hot:
            lines.append("  Minutos >= 60%:")
            for p in hot:
                lines.append(f"    {_cl(p['at'])[11:]}  {p['value']}%")
    lines.append("")
    lines.append("Otros servicios del cluster (últimos 5 min, último valor):")
    for other in report.get("other_services") or []:
        cpu = (other.get("cpu") or {}).get("latest")
        mem = (other.get("memory") or {}).get("latest")
        lines.append(f"  {other['service']}  CPU {cpu if cpu is not None else '-'}%  RAM {mem if mem is not None else '-'}%")
    lines.append("")

    alb = report.get("alb_metrics") or {}
    lines.append(f"ALB target group {TG_MARKER} — métricas de los últimos {BACKEND_LOOKBACK_MIN} min (casi en vivo):")
    if alb:
        lines.append(
            f"  Requests {alb.get('RequestCount', 0):.0f}  "
            f"2xx {alb.get('HTTPCode_Target_2XX_Count', 0):.0f}  "
            f"4xx {alb.get('HTTPCode_Target_4XX_Count', 0):.0f}  "
            f"5xx {alb.get('HTTPCode_Target_5XX_Count', 0):.0f}"
        )
        if "p99" in alb:
            lines.append(
                f"  Latencia del último minuto ({_cl(alb.get('latency_latest_at'))[11:]}): "
                f"p50 {alb['p50']}s  p90 {alb['p90']}s  p99 {alb['p99']}s"
            )
            lines.append(f"  p99 más alto de la ventana: {alb.get('p99_peak')}s a las {_cl(alb.get('p99_peak_at'))[11:]}")
        if alb.get("latency_error"):
            lines.append(f"  Latencia no disponible: {alb['latency_error']}")
    lines.append("")

    parsed = report.get("alb_logs") or {}
    rows = parsed.get("rows") or []
    lines.append(
        "Requests de backend-core en los access logs del ALB "
        "(llegan con unos 5 min de atraso; por eso el minuto exacto del aviso puede no estar todavía)."
    )
    lines.append(
        f"  Archivos leídos: {parsed.get('files', 0)}  "
        f"archivo más nuevo: {_cl(parsed.get('newest_file_at'))}  "
        f"requests de este target group: {len(rows)}"
    )
    for err in parsed.get("errors") or []:
        lines.append(f"  error leyendo logs: {err}")
    focus = None
    if report.get("focus_at"):
        focus = datetime.fromisoformat(report["focus_at"])
        matched = [r for r in rows if _overlaps(r, focus)]
        matched.sort(key=lambda r: r["seconds"], reverse=True)
        lines.append(
            f"  {len(matched)} requests en curso alrededor de {_cl(focus)[11:]} (minuto de referencia). Las más lentas:"
        )
        if not matched:
            lines.append("    ninguna en los logs ya publicados")
        for row in matched[:12]:
            lines.append(_format_request(row))
        lines.append("")
    slow = [r for r in rows if r["seconds"] >= SLOW_SECONDS]
    slow.sort(key=lambda r: r["seconds"], reverse=True)
    lines.append(f"  Requests de >= {SLOW_SECONDS:.0f}s en la ventana publicada:")
    if not slow:
        lines.append("    ninguna")
    for row in slow[:15]:
        lines.append(_format_request(row))
    lines.append("")

    path_count = Counter()
    path_time = defaultdict(float)
    status_count = Counter()
    for row in rows:
        path_count[_norm_path(row["path"])] += 1
        path_time[_norm_path(row["path"])] += row["seconds"]
        status_count[row["target_status"]] += 1
    if status_count:
        lines.append("  Status del target: " + ", ".join(f"{k}={v}" for k, v in status_count.most_common(8)))
    lines.append("  Rutas con más tiempo acumulado:")
    ranked = sorted(path_time.items(), key=lambda kv: kv[1], reverse=True)[:12]
    if not ranked:
        lines.append("    sin requests en los logs publicados")
    for path, total in ranked:
        lines.append(f"    {total:8.1f}s en {path_count[path]:4d} llamadas  {path}")
    lines.append("")

    app = report.get("app_logs") or {}
    events = app.get("events") or []
    lines.append(f"Logs de la app {APP_LOG_GROUP} (últimos 10 min, en vivo): {len(events)} líneas")
    if app.get("error"):
        lines.append(f"  no se pudieron leer: {app['error']}")
    tags = Counter()
    paths = Counter()
    interesting = []
    tag_re = re.compile(r"\[([A-Za-z0-9_:.-]{3,40})\]")
    path_re = re.compile(r"(/api/[^\s\"']+)")
    for ev in events:
        msg = (ev.get("message") or "").strip()
        for tag in tag_re.findall(msg):
            tags[tag] += 1
        for path in path_re.findall(msg):
            paths[_norm_path(path.split("?")[0])] += 1
        low = msg.lower()
        if any(k in low for k in ("error", "exception", "traceback", "timeout", "forbidden", "critical")):
            interesting.append(msg.replace("\n", " ")[:240])
    if tags:
        lines.append("  Tags: " + ", ".join(f"{k} {v}" for k, v in tags.most_common(12)))
    if paths:
        lines.append("  Rutas mencionadas en el log:")
        for path, count in paths.most_common(12):
            lines.append(f"    {count:4d}  {path}")
    lines.append("  Líneas de error / forbidden / timeout:")
    if not interesting:
        lines.append("    ninguna")
    for msg in interesting[:20]:
        lines.append(f"    {msg}")
    lines.append("  Últimas líneas:")
    for ev in events[-12:]:
        ts = datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc)
        msg = (ev.get("message") or "").replace("\n", " ")[:220]
        lines.append(f"    {_cl(ts)[11:]}  {msg}")
    lines.append("")
    return "\n".join(lines)


def _format_email(event_info, captures):
    lines = [
        "RDS CPU >= 60% — captura Performance Insights",
        f"Trigger: {event_info}",
        "",
    ]
    for cap in captures:
        lines.append("=" * 72)
        lines.append(f"Instance: {cap['db_instance']} ({cap['dbi_resource_id']})")
        lines.append(f"Window: {cap['window_start']} → {cap['window_end']}")
        cpu = cap.get("cpu") or {}
        brief = {k: cpu.get(k) for k in ("latest_max", "latest_avg", "window_peak_max", "window_peak_at")}
        lines.append(f"CPU: {json.dumps(brief)}")
        if cpu.get("window_peak_at"):
            lines.append(f"Pico hora local: {_cl(cpu['window_peak_at'])}")
        hot = [p for p in (cpu.get("series") or []) if p["max"] >= 40]
        if hot:
            lines.append("Minutos con CPU >= 40%:")
            for p in hot[-15:]:
                lines.append(f"  {_cl(p['at'])[11:]}  max {p['max']}%  avg {p['avg']}%")
        lines.append("")
        lines.append("Top SQL:")
        for i, row in enumerate(cap.get("top_sql") or [], 1):
            dims = row.get("dimensions") or {}
            sql = dims.get("db.sql.statement") or dims.get("db.sql_tokenized.statement") or str(dims)
            sql = " ".join(sql.split())
            lines.append(f"  {i}. load={row.get('total_load')} | {sql[:700]}")
        lines.append("")
        lines.append("Top waits:")
        for i, row in enumerate(cap.get("top_waits") or [], 1):
            lines.append(f"  {i}. load={row.get('total_load')} | {row.get('dimensions')}")
        lines.append("")
        lines.append("Top users:")
        for i, row in enumerate(cap.get("top_users") or [], 1):
            lines.append(f"  {i}. load={row.get('total_load')} | {row.get('dimensions')}")
        lines.append("")
        lines.append("Top databases:")
        for i, row in enumerate(cap.get("top_dbs") or [], 1):
            lines.append(f"  {i}. load={row.get('total_load')} | {row.get('dimensions')}")
        lines.append("")
    return "\n".join(lines)


def _format_rds_brief(captures):
    lines = ["RDS en la misma ventana (para cruzar con el backend)", ""]
    for cap in captures:
        cpu = cap.get("cpu") or {}
        lines.append(
            f"{cap['db_instance']}: ahora max {cpu.get('latest_max')}%  "
            f"pico {cpu.get('window_peak_max')}% a las {_cl(cpu.get('window_peak_at'))}"
        )
        lines.append("  Top SQL:")
        for i, row in enumerate((cap.get("top_sql") or [])[:5], 1):
            dims = row.get("dimensions") or {}
            sql = dims.get("db.sql.statement") or dims.get("db.sql_tokenized.statement") or str(dims)
            sql = " ".join(sql.split())
            lines.append(f"    {i}. load={row.get('total_load')} | {sql[:500]}")
        lines.append("  Top waits:")
        for i, row in enumerate((cap.get("top_waits") or [])[:4], 1):
            lines.append(f"    {i}. load={row.get('total_load')} | {row.get('dimensions')}")
        lines.append("")
    return "\n".join(lines)


def _dims(trigger):
    out = {}
    for dim in (trigger or {}).get("Dimensions") or []:
        name = dim.get("name") or dim.get("Name")
        value = dim.get("value") or dim.get("Value")
        if name:
            out[name] = value
    return out


def _parse_targets(event):
    """Return (kind, alarm_name, instances|None, metric_name, should_run)."""
    if isinstance(event, dict) and event.get("dry_run") and not event.get("AlarmName"):
        kind = event.get("kind") or "rds"
        return kind, "manual-dry-run", None, event.get("metric") or "CPUUtilization", True

    if isinstance(event, dict) and event.get("AlarmName") and event.get("Trigger"):
        if event.get("NewStateValue") not in (None, "ALARM"):
            return "skip", event.get("AlarmName"), None, None, False
        trigger = event.get("Trigger") or {}
        dims = _dims(trigger)
        metric = trigger.get("MetricName") or ""
        if dims.get("DBInstanceIdentifier"):
            return "rds", event.get("AlarmName"), [dims["DBInstanceIdentifier"]], metric, True
        if dims.get("ServiceName"):
            return "ecs", event.get("AlarmName"), None, metric, True
        return "rds", event.get("AlarmName"), None, metric, True

    if isinstance(event, dict) and "Records" in event and event["Records"]:
        rec = event["Records"][0]
        if "Sns" in rec:
            msg_raw = rec["Sns"].get("Message", "")
            if msg_raw.startswith("RDS CPU >= 60%") or msg_raw.startswith("QUÉ ESTÁ HACIENDO"):
                return "skip", None, None, None, False
            try:
                msg = json.loads(msg_raw)
            except Exception:
                return "skip", None, None, None, False
            return _parse_targets(msg)

    return "rds", (event or {}).get("source") or "manual", None, "CPUUtilization", True


def _focus_from_captures(captures):
    best = None
    best_at = None
    for cap in captures:
        cpu = cap.get("cpu") or {}
        peak = cpu.get("window_peak_max") or 0
        if peak >= 40 and cpu.get("window_peak_at") and (best is None or peak > best):
            best = peak
            best_at = datetime.fromisoformat(cpu["window_peak_at"])
    return best_at


def _subject_ecs(metric_name):
    if "Memory" in (metric_name or ""):
        what = "RAM>=60%"
    elif "CPU" in (metric_name or ""):
        what = "CPU>=60%"
    else:
        what = "recurso>=60%"
    return f"[ECS][backend-core] {what} (prod)"


def lambda_handler(event, context):
    kind, alarm_name, targets, metric_name, should_run = _parse_targets(event or {})
    if not should_run:
        return {"skipped": True, "alarm": alarm_name, "kind": kind}

    now = datetime.now(timezone.utc)
    dry = bool((event or {}).get("dry_run"))

    if kind == "ecs":
        backend = collect_backend(now)
        captures = [capture_instance(db_id, now, lookback_min=15) for db_id in INSTANCES]
        summary = "\n".join(
            [
                _format_backend(backend, f"QUÉ ESTÁ HACIENDO backend-core — {alarm_name}"),
                _format_rds_brief(captures),
            ]
        )
        subject = _subject_ecs(metric_name)
        key = f"{PREFIX}/ecs/{now.strftime('%Y/%m/%d/%H%M%SZ')}-backend-core.json"
        body = {"alarm_name": alarm_name, "kind": "ecs", "metric": metric_name, "backend": backend, "captures": captures}
    else:
        target_instances = targets or list(INSTANCES)
        captures = [capture_instance(db_id, now) for db_id in target_instances]
        backend = collect_backend(now, focus_at=_focus_from_captures(captures))
        summary = "\n".join(
            [
                _format_backend(
                    backend,
                    "QUÉ ESTÁ HACIENDO backend-core al momento de este aviso de RDS",
                ),
                _format_email(alarm_name or "manual/test", captures),
            ]
        )
        subject = f"[RDS][PI] CPU>=60% ({','.join(target_instances)})"
        joined = "-".join(target_instances)
        key = f"{PREFIX}/{now.strftime('%Y/%m/%d/%H%M%SZ')}-{joined}.json"
        body = {"alarm_name": alarm_name, "kind": "rds", "backend": backend, "captures": captures}

    s3_uri = f"s3://{BUCKET}/{key}"
    if not dry:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(body, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    summary += f"\n\nS3: {s3_uri}\n"
    if SNS_TOPIC and not dry:
        sns.publish(
            TopicArn=SNS_TOPIC,
            Subject=subject[:100],
            Message=summary[:350000],
        )
    return {"ok": True, "dry_run": dry, "s3": s3_uri, "subject": subject, "kind": kind, "message": summary if dry else None}
