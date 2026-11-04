import csv
import io
import time

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from .config import ROOT


def create_app(config, store, demo=False, channels=()):
    app = Flask(__name__, static_folder=str(ROOT / "web"), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 1024

    @app.before_request
    def local_only():
        host = request.host.split(":")[0].lower()
        if host not in ("localhost", "127.0.0.1"):
            abort(403)
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            abort(403)
        if request.method not in ("GET", "HEAD"):
            abort(405)

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return send_from_directory(ROOT / "web", "index.html")

    @app.get("/api/state")
    def state():
        now = time.time()
        latest = store.snapshot()
        devices = []
        for d in config["devices"]:
            item = latest.get(d["id"])
            freshness = "waiting" if item is None else "stale" if now - item["at"] > max(3 * config["interval_seconds"], config["timeout_seconds"] * 3) else "fresh"
            devices.append({**{k: d[k] for k in ("id", "name", "role", "host", "protocol", "interfaces")}, "parent": d.get("parent"), "freshness": freshness, "sample": item})
        return jsonify({"demo": demo, "at": now, "interval": 2 if demo else config["interval_seconds"], "thresholds": config["thresholds"], "monitor_temperature": config["monitor_temperature"], "devices": devices, "queue": store.queue(), "channels": list(channels)})

    def selected():
        device = request.args.get("device", config["devices"][0]["id"])
        if device not in {d["id"] for d in config["devices"]}:
            abort(404)
        return device

    @app.get("/api/history")
    def history():
        return jsonify(store.history(selected()))

    @app.get("/api/events")
    def events():
        return jsonify(store.events())

    @app.get("/api/export")
    def export():
        device = selected()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp_utc", "device", "protocol", "sample_kind", "connection", "cpu_pct", "ram_pct", "temperature_c"])
        for row in store.history(device, 5000):
            writer.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(row["at"])), device, row["source"], row["sample_kind"], row["kind"], row.get("cpu_pct"), row.get("ram_pct"), row.get("temperature_c")])
        return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="netwatch-{device}.csv"'})

    return app
