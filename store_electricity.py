import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    try:
        evidence = sys.stdin.read()
        reading = json.loads(evidence)["reading"]
        meter_id = reading["meter_id"]
        reading_id = reading["id"]
        for identifier in (meter_id, reading_id):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
                raise ValueError("Meter and reading IDs must use letters, digits, underscores, or hyphens")

        period_end = datetime.fromisoformat(reading["period_end_utc"])
        if period_end.tzinfo is None or period_end.microsecond:
            raise ValueError("Period end must include a timezone and use whole seconds")

        timestamp = int(period_end.timestamp())
        kwh = Decimal(reading["kwh"])
        line = f"electricity_reading,meter_id={meter_id},reading_id={reading_id} kwh={kwh} {timestamp}"

        token_file = Path.home() / ".config/exam-project/influx-token"
        token = token_file.read_text().strip()
        params = urlencode({"org": "exam-project", "bucket": "meter-readings", "precision": "s"})
        request = Request(
            f"http://127.0.0.1:18086/api/v2/write?{params}",
            data=line.encode("utf-8"),
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            if response.status != 204:
                raise OSError(f"Unexpected InfluxDB response: HTTP {response.status}")
    except (KeyError, ValueError, OSError, TimeoutError) as error:
        print(f"InfluxDB write failed: {error}", file=sys.stderr)
        return 1

    print(f"Stored {reading_id}: {kwh} kWh", file=sys.stderr)
    sys.stdout.write(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
