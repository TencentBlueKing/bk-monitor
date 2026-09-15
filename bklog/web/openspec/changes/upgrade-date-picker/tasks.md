- [x] Upgrade the dependency and lockfile to 4.0.0-beta.9.
- [x] Adapt controlled format state and preserve timezone/event contracts.
- [x] Run focused compatibility checks and AAFE impact/UI validation.
- [x] Review the diff and prepare the scoped delivery.

Focused compatibility checks: 4/4 pass (`node --test test/unit/time-range-upgrade.test.cjs`). Component ESLint, Prettier and `git diff --check` pass.

UI validation: bundled AAFE run `20260915T091053-2xg1` completed one authenticated local page-load smoke case (1/1 passed). Report: `.aafe/e2e/reports/e2e-mu2gc7nd-c4wlq2/report.json`. The local Webpack build compiled successfully. This verifies loading task code, not every date panel interaction; visual and manual selection coverage remains a residual risk.

The initial run could not start the legacy E2E server. Under the owner's task-local adapter authorization, verification used the bundled AAFE settings template and a temporary Webpack settings selector on port 41001, with the configured backend proxy. Existing local.settings files and source project defaults were preserved. Temporary tracked startup changes were removed after the successful run; the task-local adapter patch and template remain available with the reports.
