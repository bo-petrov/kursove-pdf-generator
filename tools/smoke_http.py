"""Smoke test a running service or Docker container using public synthetic examples."""

import json
from pathlib import Path
import sys
import time
import urllib.request
from io import BytesIO
from pypdf import PdfReader

base, token = sys.argv[1:3]
for attempt in range(30):
    try:
        with urllib.request.urlopen(base + "/healthz", timeout=2) as r:
            assert json.load(r)["ok"]
            break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(0.3)
for name, expected_pages in [("six", 1), ("twelve", 2)]:
    payload = (
        Path(__file__).resolve().parents[1] / f"examples/course-{name}-orders.json"
    ).read_bytes()
    data = json.loads(payload)
    req = urllib.request.Request(
        base + "/v1/courses/pdf",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        pdf = response.read()
        assert response.status == 200
        assert response.headers.get_content_type() == "application/pdf"
        assert response.headers["Cache-Control"] == "no-store"
        reader = PdfReader(BytesIO(pdf))
        assert len(reader.pages) == expected_pages
        text = " ".join(" ".join(p.extract_text().split()) for p in reader.pages)
        assert text.count("Доставен") == 3
        assert data["id"] in text
        for order in data["orders"]:
            assert order["warehouse_order"] in text
            assert order["address"] in text
    print(
        f"PASS: real HTTP {name}-order PDF; {expected_pages} pages, data and checkboxes"
    )
print("PASS: real HTTP health and PDF response")
