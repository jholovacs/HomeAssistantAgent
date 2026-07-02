.PHONY: test test-unit test-integration release release-check release-dry-run

test: test-unit test-integration

test-unit:
	python -m pytest tests/unit -v

test-integration:
	bash scripts/run_integration_tests.sh

release-check:
	python scripts/validate_release.py

release-dry-run:
	python scripts/publish_release.py --dry-run --skip-tests

release:
	python scripts/publish_release.py
