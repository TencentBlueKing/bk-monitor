# bklog Agent Notes

## Test Environment

- Do not add logic in `__init__.py` files to read `.env` files automatically.
- Do not add logic in `__init__.py` files to modify `sys.path` automatically for local linked packages.
- When running local tests, set required environment variables explicitly in the shell command.
- For this repo on Windows PowerShell, if `bklog/ai_agent` points to `../ai_agent`, set `PYTHONPATH=D:\bk-monitor` before running Django tests.

## Config Defaults

- Keep configuration defaults centralized under `bklog/config`.
- Do not introduce multiple scattered `default` configuration entry points.
- When adding or adjusting default config values, prefer `bklog/config/default.py` unless the existing config structure clearly requires another file under `bklog/config`.

## Example

```powershell
$env:APP_ID='monitor'
$env:APP_TOKEN='123456sdfdf'
$env:BK_PAAS_HOST='http://127.0.0.1:8000'
$env:PYTHONPATH='D:\bk-monitor'
.\.venv\Scripts\python.exe manage.py test apps.tests.log_search.test_es8_compat -v 2 --keepdb
```

## workflow
each time you finished your work, remain user to commit and push