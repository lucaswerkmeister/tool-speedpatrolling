.PHONY: check

check:
	flake8
	mypy
	pytest

unicodescripts.py: make-unicodescripts.py
	./$< > $@
