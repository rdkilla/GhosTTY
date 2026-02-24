.PHONY: run test lint check

run:
	./ghostty --help

test:
	python3 -m pytest -q tests

lint:
	python3 -m py_compile ghostty ghosttyd.py pyte.py

check: lint test
