# Changelog

## Stage 10 — GitHub readiness review

- Fixed a malformed, leftover admin-panel fragment in `frontend/app.js` that prevented the entire application script from parsing.
- Made frontend static-file mounting independent of the process working directory.
- Added repository hygiene files: `.gitignore` and `.dockerignore`.
- Added an unprivileged runtime user to the Docker image.
- Replaced the stage-by-stage README with consolidated setup, architecture, API, test, and limitation documentation.
- Added security policy and GitHub Actions CI checks.
- Added API smoke tests for health/frontend availability, workspace-key authentication, workspace isolation, and admin protection.
- Documented current production gaps, including migrations, rate limiting, administrator MFA, incomplete AI usage accounting, and the inactive UI language selector.
