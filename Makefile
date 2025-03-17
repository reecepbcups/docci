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
	@echo "Checking if pyinstaller is installed..."
	@[ -x "$(command -v pyinstaller)" ] || (echo "Pyinstaller is not installed. Please run 'python3 -m pip install pyinstaller --break-system-packages' to install it." && exit 1)
.PHONY: check-pyinstaller

## test: Run all unit & integration test.
test: test-unit-integration
	@python -m unittest tests/tests.py
.PHONY: test

## test-unit-integration: Run the readme tests.
test-unit-integration:
	@python -m unittest tests/integration.py

## test-examples: Run the documentation examples within this repo
test-examples:
	@echo "Running integrations as $(EXEC_BINARY)"
	@sleep 1
	$(EXEC_BINARY) tests/config1.json
	$(EXEC_BINARY) examples/1-node/config.json
	$(EXEC_BINARY) examples/2-source-code-modification/config.json
.PHONY: test-examples

.PHONY: help
help: Makefile
	@echo
	@echo " Choose a command run in "docci", or just run 'make' for install"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
