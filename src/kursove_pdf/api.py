"""Versioned backend-to-backend PDF endpoint."""

import hmac
import json
import logging
import os
import re
from urllib.parse import quote
from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException
from . import __version__
from .renderer import generate_pdf, font_codepoints
from .validation import InputError

MAX_BYTES = 1024 * 1024


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Non-finite number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_BYTES, API_TOKEN=os.environ.get("KURSOVE_API_TOKEN", "")
    )
    if config:
        app.config.update(config)
    if not app.config["API_TOKEN"]:
        raise RuntimeError(
            "Set KURSOVE_API_TOKEN to a non-empty server-to-server token"
        )
    font_codepoints()

    def error(code, message, status, details=None):
        body = {"error": {"code": code, "message": message}}
        if details is not None:
            body["error"]["details"] = details
        return jsonify(body), status

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/healthz")
    def health():
        return jsonify(ok=True, version=__version__)

    @app.post("/v1/courses/pdf")
    def pdf():
        expected = ("Bearer " + app.config["API_TOKEN"]).encode("utf-8")
        if not hmac.compare_digest(
            request.headers.get("Authorization", "").encode("utf-8"), expected
        ):
            return error("unauthorized", "Valid Bearer token required.", 401)
        if not request.is_json:
            return error("unsupported_media_type", "Use application/json.", 415)
        try:
            payload = strict_json(request.get_data())
        except (ValueError, UnicodeError, RecursionError):
            return error(
                "invalid_json",
                "Malformed JSON, duplicate key or non-finite number.",
                400,
            )
        try:
            result = generate_pdf(payload)
        except InputError as exc:
            return error("validation_error", "Invalid course data.", 422, exc.details)
        identifier = payload["id"]
        fallback = re.sub(r"[^A-Za-z0-9_.-]", "_", identifier)
        filename = f"course-{identifier}.pdf"
        response = Response(result, mimetype="application/pdf")
        response.headers["Content-Disposition"] = (
            f"inline; filename=\"course-{fallback}.pdf\"; filename*=UTF-8''{quote(filename, safe='')}"
        )
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        code = {
            413: "payload_too_large",
            404: "not_found",
            405: "method_not_allowed",
        }.get(exc.code, "http_error")
        response = jsonify(error={"code": code, "message": exc.name})
        response.status_code = exc.code
        if exc.code == 405 and exc.valid_methods:
            response.headers["Allow"] = ", ".join(exc.valid_methods)
        return response

    @app.errorhandler(Exception)
    def unexpected(exc):
        # Avoid logging exception messages/tracebacks that may contain customer input.
        logging.getLogger(__name__).error("PDF request failed (%s)", type(exc).__name__)
        return error("generation_failed", "PDF generation failed.", 500)

    return app
