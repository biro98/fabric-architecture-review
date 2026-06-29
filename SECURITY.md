# Security Policy

We take the security of this project seriously. Thank you for helping keep it and its users safe.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

Instead, report them privately using GitHub's
[**private vulnerability reporting**](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab → "Report a vulnerability"), or by contacting the
maintainers directly.

Please include as much of the following as you can to help us triage quickly:

- Type of issue (e.g. injection, secret exposure, path traversal, etc.)
- Full paths of the source file(s) related to the issue
- The location of the affected code (tag / branch / commit or direct URL)
- Any special configuration required to reproduce
- Step-by-step instructions to reproduce
- Proof-of-concept or exploit code, if possible
- Impact of the issue, including how an attacker might exploit it

## Scope note

This accelerator is **metadata-only** by design — it must never read customer business
data. Reports that demonstrate a path by which the tool could read, exfiltrate, or persist
customer data (see [docs/data-safety.md](docs/data-safety.md)) are treated as high severity.

## Disclosure

We follow coordinated disclosure: please give us a reasonable opportunity to address the
issue before any public disclosure. We will keep you informed of progress toward a fix.
