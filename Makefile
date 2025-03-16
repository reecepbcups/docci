## install: Install the binary.
install:
# pip install pyinstaller --break-system-packages
	@echo ⏳ Installing readme-runner...
	@pyinstaller -F --name readme-runner --workpath __pycache__/build --specpath __pycache__/build/ --onefile *.py
	@staticx dist/readme-runner dist/readme-runner --strip
	@chmod +x dist/readme-runner
	@if [ -z "$(IS_ACTION)" ]; then \
		sudo cp dist/readme-runner /usr/local/bin/readme-runner; \
		exit 0; \
	fi
	@echo ✅ readme-runner installed
.PHONY: install

## tests: Run the tests.
tests:
	@python -m unittest tests/tests.py
	@python -m unittest tests/integration.py
.PHONY: tests

.PHONY: help
help: Makefile
	@echo
	@echo " Choose a command run in "readme-runner", or just run 'make' for install"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
