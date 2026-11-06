# IG read-only preflight review

Baseline: `baeb5affb4f18227f737afc44cbda23e5b888e8d`.
Implementation: `2304db8`.

- Spec review: no findings. Verified explicit login modes, correct system-user account discovery, professional user ID handling, sanitized failures, and truthful read-only scope against issue #2 and the referenced Meta documentation.
- Standards review: no findings. Reviewed repository instructions and smell baseline. Protocol-specific branches represent distinct external contracts; tests exercise the public Workflow boundary and replace only the external HTTP service.
- Verification: 45 tests passed with `python -m unittest discover -s tests -t .`; mypy passed for 11 source files; dependency consistency and whitespace checks passed.

No real credential was read. This does not verify the live account asset assignment, publishing permission, media upload, or publication. Issue #2 remains open.

## 2026-11-03 diagnostic extension and integration

The statement above describes the original 2026-10-30 review only. The user subsequently replaced the credential, and the new live read-only evidence is recorded in [the account audit](2026-11-03-ig-account-audit.md); no token value is retained there.

- Incremental baseline `a1cd601` → `3cc1c0c`, followed by `3cc1c0c` → `b9ea854`: Standards and Spec both returned zero findings. The tests use the public CLI and replace only external Meta HTTP or Keychain subprocess boundaries. Failure cases cover wrong business, empty/ambiguous assets, mismatched IDs/usernames, OAuth failures, trace redaction, and OS confirmation timeout.
- Integration baseline: the previously reviewed local plugin branch at `cb9db74`. Merge `e045e94` resolves the parser conflict with the diagnostic registered inside the non-local-only branch and a distinct `diagnosis` variable. Commit `4e5f321` verifies that the extracted local plugin still rejects both IG commands before execution.
- Fresh integrated verification: 68 tests passed; mypy passed for 13 source files; whitespace checks passed. Standards and Spec independently rechecked the CLI/package integration and returned zero findings.

The PR now contains the previously reviewed #15 commits to preserve a tested merge resolution. It remains based on main and does not merge any PR, change an installed plugin, migrate an automation/database, or grant the pending Facebook Page permissions. #2 remains open and real publishing remains unimplemented/unverified.
