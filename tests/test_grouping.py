from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path

import pytest
from pypdf import PdfReader
from kursove_pdf import generate_pdf, InputError
from kursove_pdf.grouping import group_orders

ROOT = Path(__file__).resolve().parents[1]


def course():
    return json.loads((ROOT / "examples/course-six-orders.json").read_text())


def checkbox_count(reader):
    # Static, pen-sized empty squares; no interactive checkbox fields.
    assert not reader.get_fields()
    count = 0
    for page in reader.pages:
        assert not page.get("/Annots")
        count += sum(
            op == b"re"
            and abs(float(args[2]) - 23) < 0.01
            and abs(float(args[3]) - 23) < 0.01
            for args, op in page.get_contents().operations
        )
    return count


def test_approved_three_groups_one_page():
    data = course()
    before = deepcopy(data)
    reader = PdfReader(BytesIO(generate_pdf(data)))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for name in {o["client"] for o in data["orders"]}:
        assert text.count(name) == 1
    assert text.count("Доставен") == checkbox_count(reader) == 3
    assert [len(g.orders) for g in group_orders(data["orders"])] == [3, 2, 1]
    assert data == before


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({}, 1),
        ({"client_id": "different"}, 2),
        ({"client": "Different name"}, 2),
        ({"client": "Примерна мебелна къща ООД "}, 2),
    ],
)
def test_ids_and_exact_names_control_grouping(changes, expected):
    orders = [deepcopy(course()["orders"][0]) for _ in range(2)]
    orders[1].update(changes)
    assert len(group_orders(orders)) == expected


def test_legacy_payload_and_mixed_identity():
    data = course()
    for o in data["orders"]:
        o.pop("client_id")
    assert checkbox_count(PdfReader(BytesIO(generate_pdf(data)))) == 3
    data["orders"][1]["client_id"] = "known"
    assert [len(g.orders) for g in group_orders(data["orders"])] == [1, 1, 1, 2, 1]


def test_revisits_preserve_order_and_get_separate_checkbox():
    data = course()
    data["orders"] = [data["orders"][0], data["orders"][3], data["orders"][1]]
    reader = PdfReader(BytesIO(generate_pdf(data)))
    text = reader.pages[0].extract_text()
    positions = [text.index(o["warehouse_order"]) for o in data["orders"]]
    assert positions == sorted(positions)
    assert checkbox_count(reader) == 3


def test_conflicting_company_phones_are_preserved_per_order():
    data = course()
    data["orders"] = data["orders"][:3]
    phones = ["0877222222", "0888333333", None]
    for o, p in zip(data["orders"], phones):
        o["company_phone"] = p
    reader = PdfReader(BytesIO(generate_pdf(data)))
    text = reader.pages[0].extract_text()
    for phone in phones[:2]:
        assert text.count(phone) == 1
    assert "не е посочен" in text
    assert checkbox_count(reader) == 1
    for i, o in enumerate(data["orders"][:2]):
        start = text.index(o["warehouse_order"])
        end = text.index(data["orders"][i + 1]["warehouse_order"])
        assert phones[i] in text[start:end]


def test_continuation_repeats_customer_but_not_checkbox():
    data = course()
    data["orders"] = [deepcopy(data["orders"][0]) for _ in range(20)]
    for i, o in enumerate(data["orders"]):
        o["warehouse_order"] = f"DOC-{i:03}"
    reader = PdfReader(BytesIO(generate_pdf(data)))
    assert len(reader.pages) > 1
    assert checkbox_count(reader) == 1
    for page in reader.pages:
        text = page.extract_text()
        assert data["orders"][0]["client"] in text
        assert "DOC-" in text
    for o in data["orders"]:
        assert sum(o["warehouse_order"] in p.extract_text() for p in reader.pages) == 1


@pytest.mark.parametrize("value", [None, "", "   ", 123, "a" * 121])
def test_invalid_client_id(value):
    data = course()
    data["orders"][0]["client_id"] = value
    with pytest.raises(InputError):
        generate_pdf(data)


def test_six_different_clients_keep_all_data():
    data = course()
    for i, o in enumerate(data["orders"]):
        o.update(client=f"Клиент {i}", client_id=f"customer-{i}")
    reader = PdfReader(BytesIO(generate_pdf(data)))
    text = " ".join(p.extract_text() for p in reader.pages)
    assert checkbox_count(reader) == 6
    for o in data["orders"]:
        assert text.count(o["client"]) == 1
        assert text.count(o["warehouse_order"]) == 1


def test_openapi_matches_runtime_schema_and_version():
    from kursove_pdf import __version__

    schema = json.loads((ROOT / "src/kursove_pdf/schema.json").read_text())
    schema.pop("$schema")
    spec = json.loads((ROOT / "docs/openapi.json").read_text())
    assert spec["components"]["schemas"]["CoursePdfRequest"] == schema
    assert spec["info"]["version"] == __version__
