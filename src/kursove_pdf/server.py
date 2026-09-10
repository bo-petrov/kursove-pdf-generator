import os
from waitress import serve
from .api import create_app, MAX_BYTES


def main():
    app = create_app()
    serve(
        app,
        host=os.environ.get("KURSOVE_HOST", "127.0.0.1"),
        port=int(os.environ.get("KURSOVE_PORT", "8080")),
        threads=4,
        max_request_body_size=MAX_BYTES + 65536,
        channel_timeout=60,
    )
