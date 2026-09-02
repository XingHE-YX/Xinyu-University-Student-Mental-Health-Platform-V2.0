# CloudBase phase 7.1 operator checklist

Use an ignored, rendered copy of `manifest.template.json`; never commit the rendered file. Complete each environment independently.

- [ ] Create two distinct CloudBase EnvIDs and record them in the deployment vault.
- [ ] Create separate database namespaces; provision the collection/index list from `environment.template.yaml` and `BACKEND_STRUCTURE.md`.
- [ ] Upload the Python 3.11 HTTP function with `scf_bootstrap`, locked dependencies, port `9000`, and environment-specific function name.
- [ ] Set `DEMO_MODE=true` only in demo and `false` only in authorized. Confirm the server validates EnvID/mode together.
- [ ] Add API keys, app secrets, password hashes, and session secrets only as encrypted CloudBase variables. Do not place values in source, bundles, logs, or tickets.
- [ ] Publish `admin/dist` to separate HTTPS static-hosting origins and configure the matching API CORS/allow-list.
- [ ] Run `python deploy/cloudbase/validate_manifest.py <ignored-rendered-manifest.json>`; resolve every error without exposing values.
- [ ] Call `/api/v1/health` in each environment, then run the interface contract tests.
- [ ] Verify demo reset succeeds only in demo and is rejected before any deletion in authorized.
- [ ] Capture function/runtime, hosting, database, and reset-isolation evidence for the release record.
