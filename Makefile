# Either python3 main.py or docci
EXEC_BINARY?=python3 main.py

## install: Install the binary.
install: check-pyinstaller
	@echo ⏳ Installing docci...
	@pyinstaller --name docci --workpath __pycache__/build --specpath __pycache__/build/ --onefile *.py
	@sudo cp dist/docci /usr/local/bin/docci;
# this must come after the sudo cp else you could hit /proc/self/exec: Permission denied issues
	sudo chmod a+xr /usr/local/bin/docci;
	@echo ✅ docci installed
.PHONY: install

check-pyinstaller:
	@if ! command -v pyinstaller > /dev/null 2>&1; then \
		echo "Pyinstaller is not installed. Please run 'python3 -m pip install pyinstaller --break-system-packages' to install it."; \
		exit 1; \
	fi
.PHONY: check-pyinstaller

## test: Run all unit & integration test.
test: test-unit-integration
	@python -m unittest tests/tests.py
.PHONY: test

## test-unit-integration: Run the readme tests.
test-unit-integration:
	@python -m unittest tests/integration.py

## test-examples: Run the documentation examples within this repo
test-examples: test-main-readme
	@echo "Running integrations as $(EXEC_BINARY)"
	@sleep 1
	$(EXEC_BINARY) tests/config1.json
	$(EXEC_BINARY) examples/1-node/config.json
	$(EXEC_BINARY) examples/2-source-code-modification/config.json
.PHONY: test-examples

## test-main-readme: Run the main readme examples.
test-main-readme:
	@echo "Running main readme examples as $(EXEC_BINARY)"
	@sleep 1
	@cat README.md | sed -e 's/````bash//g' | sed -e 's/````//g' > _tmp_README.md
	$(EXEC_BINARY) tests/main-readme.json
.PHONY: test-main-readme

.PHONY: help
help: Makefile
	@echo
	@echo " Choose a command run in "docci", or just run 'make' for install"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
