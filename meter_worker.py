import argparse
import fcntl
import hashlib
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
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
            identity = json.dumps(key, separators=(",", ":")).encode("utf-8")
            anchor_id = hashlib.sha256(identity).hexdigest()
            bundle = subprocess.check_output(
                ["bash", str(ROOT / "fabric_evidence.sh"), "issue", anchor_id, str(pending)],
                env={**os.environ, "TMPDIR": str(STATE)},
                text=True,
            ).strip()
            db.execute("INSERT INTO processed VALUES (?, ?, ?, ?, ?)", (*key, digest, bundle))
        finally:
            pending.unlink(missing_ok=True)

    return f"ACCEPTED {reading['id']}: {bundle} (Fabric anchor: {anchor_id})"


def replay_pending(db):
    pending = db.execute(
        "SELECT id, topic, payload FROM pending_readings ORDER BY id"
    ).fetchall()
    for job_id, topic, payload in pending:
        finish_pending(db, job_id, topic, payload)


def finish_pending(db, job_id, topic, payload):
    try:
        result = process_message(db, topic, payload)
    except (OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(f"QUEUED job {job_id}: {error}", file=sys.stderr, flush=True)
        return

    with db:
        db.execute("DELETE FROM pending_readings WHERE id = ?", (job_id,))
    print(result, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Process MQTT meter readings")
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--retry-interval", type=int, default=15, metavar="SECONDS")
    args = parser.parse_args()
    if args.retry_interval <= 0:
        parser.error("--retry-interval must be positive")
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STATE / "processed.sqlite3", timeout=30)
    db.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            scope INTEGER, meter_id TEXT, reading_id TEXT, digest TEXT, bundle TEXT,
            PRIMARY KEY (scope, meter_id, reading_id)
        )
    """)

    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS pending_readings (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                payload BLOB NOT NULL
            )
        """)

    replay_pending(db)
    if args.retry_only:
        remaining = db.execute("SELECT count(*) FROM pending_readings").fetchone()[0]
        print(f"Pending readings: {remaining}")
        db.close()
        return int(remaining > 0)

    command = ["mosquitto_sub", "-h", "127.0.0.1", "-p", "18883", "-q", "1", "-v", "-R"]
    for topic in SCRIPTS:
        command.extend(["-t", topic])

    subscriber = subprocess.Popen(command, stdout=subprocess.PIPE)
    try:
        messages = queue.Queue(maxsize=128)

        def read_subscriber():
            for line in subscriber.stdout:
                messages.put(line)
            messages.put(None)

        threading.Thread(target=read_subscriber, daemon=True).start()
        next_retry = time.monotonic() + args.retry_interval
        print("Listening for live fuel and electricity readings", flush=True)

        while True:
            now = time.monotonic()
            if now >= next_retry:
                replay_pending(db)
                next_retry = time.monotonic() + args.retry_interval

            try:
                line = messages.get(timeout=max(0, next_retry - time.monotonic()))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                topic, payload = line.rstrip(b"\r\n").split(b" ", 1)
                topic = topic.decode("ascii")
                evidence = run_python(SCRIPTS[topic], payload)
                run_python(
                    "flag_meter_anomaly.py", evidence,
                    str(ROOT / "fixtures/meter_history_demo.json"),
                )
                with db:
                    job_id = db.execute(
                        "INSERT INTO pending_readings (topic, payload) VALUES (?, ?)",
                        (topic, payload),
                    ).lastrowid
                finish_pending(db, job_id, topic, payload)
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
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another meter worker is already running.", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(main())
