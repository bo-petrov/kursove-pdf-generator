from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import pytest
from pypdf import PdfReader
from kursove_pdf import generate_pdf, InputError
from kursove_pdf.api import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def course():
    return json.loads((ROOT / "examples/course-six-orders.json").read_text())


def extract(pdf):
    reader = PdfReader(BytesIO(pdf))
    return reader, " ".join(" ".join(p.extract_text().split()) for p in reader.pages)


def test_six_orders_fit_and_all_values_survive(course):
    r, text = extract(generate_pdf(course))
    assert len(r.pages) == 1
    assert "ТРАНСПОРТЕН КУРС" not in text
    assert "ОБРАЗЕЦ" not in text
    assert "5 ПОЗИЦИИ" in text and "10.09.2026" in text
    for key in ["id", "name", "created_by", "note"]:
        assert course[key] in text
    for o in course["orders"]:
        for key, value in o.items():
            if key != "client_id":
                assert str(value) in text
    assert all(p.mediabox.width == r.pages[0].mediabox.width for p in r.pages)
    assert abs(float(r.pages[0].mediabox.width) - 595.276) < 1


def test_order_preservation_and_page_numbers(course):
    course["orders"] = [deepcopy(course["orders"][0]) for _ in range(20)]
    ids = [f"0099-{20 - i:02}" for i in range(20)]
    for o, oid in zip(course["orders"], ids):
        o["warehouse_order"] = oid
    r, text = extract(generate_pdf(course))
    assert len(r.pages) > 1
    positions = [text.index(oid) for oid in ids]
    assert positions == sorted(positions)
    for i, page in enumerate(r.pages, 1):
        assert course["id"] in page.extract_text()
        assert f"{i} / {len(r.pages)}" in page.extract_text()
    for oid in ids:
        assert text.count(oid) == 1


def test_massive_note_and_address_split_without_data_loss(course):
    course["orders"] = course["orders"][:1]
    course["note"] = " ".join(f"Бележка{i:04}" for i in range(700))
    course["orders"][0]["address"] = " ".join(f"Адрес{i:04}" for i in range(900))
    r, text = extract(generate_pdf(course))
    assert len(r.pages) >= 4
    for prefix, n in [("Бележка", 700), ("Адрес", 900)]:
        for i in range(n):
            assert text.count(f"{prefix}{i:04}") == 1
    assert "продължение" in text
    assert course["orders"][0]["recipient"] in text


def test_long_labels_contacts_and_leading_zeroes(course):
    course["orders"] = course["orders"][:1]
    course.update(id="0001-София", name="Курс " * 45, created_by="Диспечер " * 26)
    o = course["orders"][0]
    o.update(
        client="Клиент " * 32,
        recipient="Получател " * 24,
        recipient_phone="0" * 80,
        warehouse_order="00001234",
        invoice="00000567",
        company_phone="0000888777",
    )
    r, text = extract(generate_pdf(course))
    for value in ["0001-София", "00001234", "00000567", "0000888777"]:
        assert value in text
    assert "0" * 80 in text.replace(" ", "")


def test_literal_markup_and_missing_contacts(course):
    course["orders"] = course["orders"][:1]
    course["note"] = "<b>literal</b> & text"
    for key in ["company_phone", "recipient_phone", "recipient"]:
        course["orders"][0][key] = None
    _, text = extract(generate_pdf(course))
    assert "<b>literal</b> & text" in text
    assert text.count("не е посочен") == 3


@pytest.mark.parametrize(
    "patch",
    [
        {"date": "2026-02-30"},
        {"date": "10.09.2026"},
        {"orders": []},
        {"id": 123},
        {"id": "   "},
        {"unexpected": True},
        {"name": "🙂"},
        {"note": "bad\x00data"},
    ],
)
def test_invalid_course_rejected(course, patch):
    course.update(patch)
    with pytest.raises(InputError):
        generate_pdf(course)


@pytest.mark.parametrize("count", [-1, True, "5", 1.5])
def test_bad_position_count(course, count):
    course["orders"][0]["product_count"] = count
    with pytest.raises(InputError):
        generate_pdf(course)


def test_single_position_and_zero(course):
    course["orders"][0]["product_count"] = 1
    course["orders"][1]["product_count"] = 0
    _, text = extract(generate_pdf(course))
    assert "1 ПОЗИЦИЯ" in text and "0 ПОЗИЦИИ" in text


def test_shared_renderer_does_not_mix_requests(course):
    inputs = []
    for i in range(8):
        item = deepcopy(course)
        item["id"] = f"parallel-{i}"
        inputs.append(item)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(generate_pdf, inputs))
    for i, pdf in enumerate(results):
        _, text = extract(pdf)
        assert f"parallel-{i}" in text
        for j in range(8):
            if i != j:
                assert f"parallel-{j}" not in text


@pytest.fixture
def client():
    return create_app({"TESTING": True, "API_TOKEN": "test-token"}).test_client()


HEADERS = {"Authorization": "Bearer test-token"}


def test_http_pdf(client, course):
    r = client.post("/v1/courses/pdf", json=course, headers=HEADERS)
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF-")
    assert "filename*=UTF-8''course-123-%D0%A1" in r.headers["Content-Disposition"]
    assert r.headers["Cache-Control"] == "no-store"
    assert len(PdfReader(BytesIO(r.data)).pages) == 1


def test_http_errors(client, course):
    assert client.get("/healthz").json["ok"] is True
    assert client.post("/v1/courses/pdf", json=course).status_code == 401
    assert client.post("/v1/courses/pdf", data="x", headers=HEADERS).status_code == 415
    for raw in ["{", '{"id":"a","id":"b"}', "NaN", "[" * 2000]:
        response = client.post(
            "/v1/courses/pdf",
            data=raw,
            content_type="application/json",
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert response.json["error"]["code"] == "invalid_json"
    response = client.post("/v1/courses/pdf", json={"id": "x"}, headers=HEADERS)
    assert response.status_code == 422 and response.json["error"]["details"]
    response = client.post(
        "/v1/courses/pdf",
        data=" " * 1048577,
        content_type="application/json",
        headers=HEADERS,
    )
    assert response.status_code == 413
    assert response.json["error"]["code"] == "payload_too_large"
    assert client.get("/missing").status_code == 404
    assert client.get("/v1/courses/pdf").status_code == 405


def test_secret_is_required(monkeypatch):
    monkeypatch.delenv("KURSOVE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_cli(tmp_path):
    dest = tmp_path / "sample.pdf"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "kursove_pdf.cli",
            str(ROOT / "examples/course-six-orders.json"),
            str(dest),
        ],
        capture_output=True,
    )
    assert result.returncode == 0
    assert len(PdfReader(dest).pages) == 1


def test_no_input_in_unexpected_error(client, course, monkeypatch, caplog):
    def fail(*args):
        raise ValueError("PRIVATE CUSTOMER DETAIL")

    monkeypatch.setattr("kursove_pdf.api.generate_pdf", fail)
    response = client.post("/v1/courses/pdf", json=course, headers=HEADERS)
    assert response.status_code == 500
    assert "PRIVATE CUSTOMER DETAIL" not in response.text + caplog.text


def test_qr_decodes_exact_id_on_every_page(course):
    import pypdfium2 as pdfium
    import zxingcpp

    course["id"] = "0000123-София"
    course["orders"] = [deepcopy(o) for _ in range(2) for o in course["orders"]]
    doc = pdfium.PdfDocument(generate_pdf(course))
    try:
        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=2)
            results = zxingcpp.read_barcodes(bitmap.to_pil())
            assert [r.text for r in results] == [course["id"]]
            bitmap.close()
            page.close()
    finally:
        doc.close()


def test_numeric_integer_normalization(course):
    course["orders"][0]["product_count"] = 1.0
    _, text = extract(generate_pdf(course))
    assert "1 ПОЗИЦИЯ" in text
    assert course["orders"][0]["product_count"] == 1.0


def test_maximum_order_limit(course):
    course["orders"] = [deepcopy(course["orders"][0]) for _ in range(100)]
    r, text = extract(generate_pdf(course))
    assert "100" in text
    assert len(r.pages) > 1
    assert text.count(course["orders"][0]["warehouse_order"]) == 100
    course["orders"].append(course["orders"][0])
    with pytest.raises(InputError):
        generate_pdf(course)
