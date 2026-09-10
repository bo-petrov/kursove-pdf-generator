"""One schema for HTTP, CLI and direct Python callers."""

import json
from importlib.resources import files
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads(files("kursove_pdf").joinpath("schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


class InputError(ValueError):
    def __init__(self, details):
        self.details = details
        super().__init__("Invalid course data")


def validate(payload):
    errors = []
    for error in VALIDATOR.iter_errors(payload):
        path = "/" + "/".join(str(p) for p in error.absolute_path)
        # Do not reflect user-supplied values back into error text or logs.
        messages = {
            "required": "Required field is missing.",
            "additionalProperties": "Unknown field.",
            "type": "Incorrect type.",
            "format": "Invalid date; use YYYY-MM-DD.",
            "minLength": "Must not be empty.",
            "maxLength": "Text is too long.",
            "pattern": "Invalid text format.",
            "minimum": "Below minimum.",
            "maximum": "Above maximum.",
            "minItems": "At least one order is required.",
            "maxItems": "At most 100 orders are supported.",
        }
        if error.validator == "required":
            for key in error.validator_value:
                if key not in error.instance:
                    item = {
                        "field": path.rstrip("/") + "/" + key,
                        "reason": messages["required"],
                    }
                    if item not in errors:
                        errors.append(item)
        else:
            errors.append(
                {
                    "field": path,
                    "reason": messages.get(error.validator, "Invalid value."),
                }
            )
        if len(errors) == 25:
            break
    if errors:
        raise InputError(errors)
    # Reject control characters and missing glyphs instead of producing blank boxes.
    from .renderer import font_codepoints

    supported = font_codepoints()

    def scan(value, path=""):
        if isinstance(value, dict):
            for k, v in value.items():
                scan(v, f"{path}/{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                scan(v, f"{path}/{i}")
        elif isinstance(value, str):
            if any(
                (ord(c) < 32 and c not in "\n\t")
                or (ord(c) >= 32 and ord(c) not in supported)
                for c in value
            ):
                errors.append(
                    {
                        "field": path,
                        "reason": "Unsupported character or control character.",
                    }
                )

    scan(payload)
    if errors:
        raise InputError(errors[:25])
    return {
        **payload,
        "orders": [
            {**order, "product_count": int(order["product_count"])}
            for order in payload["orders"]
        ],
    }
