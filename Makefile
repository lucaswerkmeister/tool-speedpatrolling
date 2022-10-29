.PHONY: check

check:
	flake8
	pytest

unicodescripts.py: make-unicodescripts.py
	./$< > $@
