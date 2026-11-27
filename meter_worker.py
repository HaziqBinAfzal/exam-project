import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATE = Path.home() / ".local/share/exam-project/meter-worker"
SCRIPTS = {
    "exam-project/meters/electricity": "ingest_electricity.py",
    "exam-project/meters/fuel": "ingest_fuel.py",
}


def run_python(script, payload, *args):
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / script), *args],
        input=payload,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout


def process_message(db, topic, payload):
    ingest_script = SCRIPTS[topic]
    evidence = run_python(ingest_script, payload)
    record = json.loads(evidence)
    reading = record["reading"]
    key = (record["scope"], reading["meter_id"], reading["id"])
    normalized = json.dumps(reading, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    with db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT digest FROM processed WHERE scope = ? AND meter_id = ? AND reading_id = ?",
            key,
        ).fetchone()
        if previous:
            if previous[0] == digest:
                return f"SKIPPED duplicate: {reading['id']}"
            return f"CONFLICT: {reading['id']} was previously stored with different data"

        evidence = run_python(
            "flag_meter_anomaly.py", evidence, str(ROOT / "fixtures/meter_history_demo.json")
        )
        stored_evidence = run_python("store_electricity.py", evidence)
        pending = STATE / "pending.json"
        pending.write_bytes(stored_evidence)
        try:
            bundle = subprocess.check_output(
                ["bash", str(ROOT / "issue_audit_bundle.sh"), str(pending)],
                env={**os.environ, "TMPDIR": str(STATE)},
                text=True,
            ).strip()
            db.execute("INSERT INTO processed VALUES (?, ?, ?, ?, ?)", (*key, digest, bundle))
        finally:
            pending.unlink(missing_ok=True)

    return f"ACCEPTED {reading['id']}: {bundle}"


def main():
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STATE / "processed.sqlite3", timeout=30)
    db.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            scope INTEGER, meter_id TEXT, reading_id TEXT, digest TEXT, bundle TEXT,
            PRIMARY KEY (scope, meter_id, reading_id)
        )
    """)

    command = ["mosquitto_sub", "-h", "127.0.0.1", "-p", "18883", "-q", "1", "-v", "-R"]
    for topic in SCRIPTS:
        command.extend(["-t", topic])

    subscriber = subprocess.Popen(command, stdout=subprocess.PIPE)
    try:
        print("Listening for live fuel and electricity readings", flush=True)
        for line in subscriber.stdout:
            try:
                topic, payload = line.rstrip(b"\r\n").split(b" ", 1)
                print(process_message(db, topic.decode("ascii"), payload), flush=True)
            except (ValueError, KeyError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
                print(f"Reading processing failed: {error}", file=sys.stderr, flush=True)
        print("MQTT subscriber stopped", file=sys.stderr)
        return subscriber.wait() or 1
    except KeyboardInterrupt:
        return 0
    finally:
        if subscriber.poll() is None:
            subscriber.terminate()
        subscriber.wait()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
