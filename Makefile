.PHONY: check

check:
	pytest

unicodescripts.py: make-unicodescripts.py
	./$< > $@
