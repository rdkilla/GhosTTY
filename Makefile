.PHONY: run test lint check

run:
	python3 ghostty.py --help

test:
	python3 -m pytest -q tests

lint:
	python3 -m py_compile ghostty.py ghosttyd.py pyte.py

check: lint test
