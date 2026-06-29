# Cover logo (optional)

The cover logo is **optional and not shipped** — there is no default logo, so the PDF
builds with no logo unless you provide one. It does **not** need to be any particular
brand.

To add one, either:

- drop a PNG named `logo.png` in this folder, or
- point the `REPORT_LOGO` environment variable (or the `--logo` flag) at any PNG path.

The PDF generator (`reports/_generate_pdf.py`) embeds the PNG as a base64 inline image
just above the first `<h1>` of the rendered report. If no logo is configured, the PDF
still builds — just without a cover logo.
