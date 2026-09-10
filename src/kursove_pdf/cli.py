import argparse
import json
import sys
from pathlib import Path
from .api import strict_json, MAX_BYTES
from .renderer import generate_pdf
from .validation import InputError


def main():
    parser = argparse.ArgumentParser(
        description="Generate a course PDF from UTF-8 JSON."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--sample", action="store_true", help="Mark this PDF as example data"
    )
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > MAX_BYTES:
            raise ValueError("JSON exceeds 1 MiB")
        payload = strict_json(args.input.read_bytes())
        result = generate_pdf(payload, sample=args.sample)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(result)
    except InputError as exc:
        print(
            json.dumps(
                {"error": "validation_error", "details": exc.details},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except (ValueError, OSError, RecursionError) as exc:
        print(f"Generation failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
