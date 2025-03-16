# Either python3 main.py or docs-ci
EXEC_BINARY?=python3 main.py

## install: Install the binary.
install:
# pip install pyinstaller staticx --break-system-packages
	@echo ⏳ Installing docs-ci...
	@pyinstaller --name docs-ci --workpath __pycache__/build --specpath __pycache__/build/ --onefile *.py
	@sudo cp dist/docs-ci /usr/local/bin/docs-ci;
# this must come after the sudo cp else you could hit /proc/self/exec: Permission denied issues
	sudo chmod a+xr /usr/local/bin/docs-ci;
	@echo ✅ docs-ci installed
.PHONY: install

## tests: Run the tests.
tests:
	@python -m unittest tests/tests.py
	@python -m unittest tests/integration.py
.PHONY: tests

## run-integrations: Run the documentation examples within this repo
run-integrations:
	@echo "Running integrations as $(EXEC_BINARY)"
	@sleep 1
	$(EXEC_BINARY) tests/config1.json
	$(EXEC_BINARY) examples/1-node/config.json
	$(EXEC_BINARY) examples/2-source-code-modification/config.json
.PHONY: run-integrations

.PHONY: help
help: Makefile
	@echo
	@echo " Choose a command run in "docs-ci", or just run 'make' for install"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
