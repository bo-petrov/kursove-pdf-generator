# Generator maintenance

Read README.md, docs/API.md and docs/INTEGRATION.md before changing the service.
The package must work without any parent workspace or machine-specific files.

- src/kursove_pdf/schema.json is the authoritative v1 request schema.
- Keep docs/openapi.json synchronized with the schema and HTTP implementation.
- Preserve input order, literal course ID in QR, leading zeroes and all business data.
- Render and visually inspect changed PDF layouts, including continuation pages.
- Keep real customer data, secrets and internal operational notes out of the repository.
- Use pytest for meaningful validation/HTTP/rendering checks; run tools/smoke_http.py
  against the actual Waitress service or container after service changes.
- Generator changes must keep CLI, Python callers and HTTP behavior consistent.
- Retain bundled font licenses; never rely on fonts installed on the developer's Mac.
