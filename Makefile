## install: Install the binary.
install:
# pip install pyinstaller staticx --break-system-packages
	@echo ⏳ Installing docs-ci...
	@pyinstaller --name docs-ci --workpath __pycache__/build --specpath __pycache__/build/ --onefile *.py
	@staticx dist/docs-ci dist/docs-ci --strip
	@if [ -z "$(IS_ACTION)" ]; then \
		sudo cp dist/docs-ci /usr/local/bin/docs-ci; \
	fi
# this must come after the sudo cp else you could hit /proc/self/exec: Permission denied issues
	sudo chmod a+xr /usr/local/bin/docs-ci;
	@echo ✅ docs-ci installed
.PHONY: install

## tests: Run the tests.
tests:
	@python -m unittest tests/tests.py
	@python -m unittest tests/integration.py
.PHONY: tests

.PHONY: help
help: Makefile
	@echo
	@echo " Choose a command run in "docs-ci", or just run 'make' for install"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
