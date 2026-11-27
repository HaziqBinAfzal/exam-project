import io
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from meter_worker import finish_pending, replay_pending


class MeterRetryTests(unittest.TestCase):
    def test_failed_reading_survives_restart_and_is_removed_after_replay(self):
        topic = "exam-project/meters/electricity"
        payload = b'{"id":"RETRY-TEST"}'
        write_failure = subprocess.CalledProcessError(1, ["store_electricity.py"])

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "worker.sqlite3"

            with closing(sqlite3.connect(database)) as db:
                with db:
                    db.execute("""
                        CREATE TABLE pending_readings (
                            id INTEGER PRIMARY KEY,
                            topic TEXT NOT NULL,
                            payload BLOB NOT NULL
                        )
                    """)
                    job_id = db.execute(
                        "INSERT INTO pending_readings (topic, payload) VALUES (?, ?)",
                        (topic, payload),
                    ).lastrowid

                error_log = io.StringIO()
                with patch("meter_worker.process_message", side_effect=write_failure):
                    with redirect_stderr(error_log):
                        finish_pending(db, job_id, topic, payload)
                self.assertIn(f"QUEUED job {job_id}", error_log.getvalue())

            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(
                    db.execute("SELECT id, topic, payload FROM pending_readings").fetchall(),
                    [(job_id, topic, payload)],
                )

                output = io.StringIO()
                with patch("meter_worker.process_message", return_value="ACCEPTED RETRY-TEST") as process:
                    with redirect_stdout(output):
                        replay_pending(db)
                        replay_pending(db)

                process.assert_called_once_with(db, topic, payload)
                self.assertIn("ACCEPTED RETRY-TEST", output.getvalue())
                self.assertEqual(db.execute("SELECT count(*) FROM pending_readings").fetchone()[0], 0)
