"""Generate OpenAPI from the exact runtime schema. No network access."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "src/kursove_pdf/schema.json").read_text())
schema.pop("$schema", None)
error_schema = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["field", "reason"],
                        "properties": {
                            "field": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
}
examples = {
    400: ("invalid_json", "Malformed JSON, duplicate key or non-finite number."),
    401: ("unauthorized", "Valid Bearer token required."),
    413: ("payload_too_large", "Request Entity Too Large"),
    415: ("unsupported_media_type", "Use application/json."),
    422: ("validation_error", "Invalid course data."),
    500: ("generation_failed", "PDF generation failed."),
}
responses = {
    "200": {
        "description": "A4 PDF; input order preserved. No storage or caching.",
        "headers": {
            "Content-Disposition": {"schema": {"type": "string"}},
            "Cache-Control": {"schema": {"type": "string", "const": "no-store"}},
        },
        "content": {
            "application/pdf": {"schema": {"type": "string", "format": "binary"}}
        },
    }
}
for status, (code, message) in examples.items():
    example = {"error": {"code": code, "message": message}}
    if status == 422:
        example["error"]["details"] = [
            {"field": "/date", "reason": "Invalid date; use YYYY-MM-DD."}
        ]
    responses[str(status)] = {
        "description": message,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": example,
            }
        },
    }
spec = {
    "openapi": "3.1.0",
    "info": {"title": "Kursove PDF Generator", "version": "1.1.0"},
    "servers": [{"url": "http://127.0.0.1:8080"}],
    "paths": {
        "/healthz": {
            "get": {
                "summary": "Service health",
                "responses": {
                    "200": {
                        "description": "Ready",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["ok", "version"],
                                    "properties": {
                                        "ok": {"type": "boolean"},
                                        "version": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/v1/courses/pdf": {
            "post": {
                "summary": "Generate a course PDF",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CoursePdfRequest"},
                            "example": json.loads(
                                (ROOT / "examples/course-six-orders.json").read_text()
                            ),
                        }
                    },
                },
                "responses": responses,
            }
        },
    },
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        "schemas": {"CoursePdfRequest": schema, "Error": error_schema},
    },
}
(ROOT / "docs/openapi.json").write_text(
    json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
)
