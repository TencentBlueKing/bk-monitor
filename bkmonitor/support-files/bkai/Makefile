PYTHON ?= python3
export PYTHONDONTWRITEBYTECODE = 1

.PHONY: check test validate plan show sync build
.DEFAULT_GOAL := check

check:
	$(PYTHON) scripts/check_package.py

test:
	$(PYTHON) -c "from bkai_init import __version__; assert __version__ == '0.1.6', 'bkai-init 0.1.6 is required'"
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m unittest discover -s package/skills/bk-grafana-dashboard/scripts/tests -v
	$(PYTHON) -m unittest discover -s package/skills/bk-data-fetcher/scripts -p 'test_*.py' -v

validate:
	$(PYTHON) scripts/run_bkai.py validate

plan:
	$(PYTHON) scripts/run_bkai.py plan

show:
	$(PYTHON) scripts/run_bkai.py show

sync:
	$(PYTHON) scripts/run_bkai.py sync

# Use the platform-provided image containing bkai-init 0.1.6.
build: check
	@test -n "$(BKAI_INIT_IMAGE)" || (echo 'BKAI_INIT_IMAGE is required' >&2; exit 1)
	docker build --build-arg BKAI_INIT_IMAGE="$(BKAI_INIT_IMAGE)" -t bk-monitor-skills-init:local .
