# IG read-only preflight review

Baseline: `baeb5affb4f18227f737afc44cbda23e5b888e8d`.
Implementation: `2304db8`.

- Spec review: no findings. Verified explicit login modes, correct system-user account discovery, professional user ID handling, sanitized failures, and truthful read-only scope against issue #2 and the referenced Meta documentation.
- Standards review: no findings. Reviewed repository instructions and smell baseline. Protocol-specific branches represent distinct external contracts; tests exercise the public Workflow boundary and replace only the external HTTP service.
- Verification: 45 tests passed with `python -m unittest discover -s tests -t .`; mypy passed for 11 source files; dependency consistency and whitespace checks passed.

No real credential was read. This does not verify the live account asset assignment, publishing permission, media upload, or publication. Issue #2 remains open.
