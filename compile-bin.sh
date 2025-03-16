pyinstaller --name readme-runner --specpath build/ --onefile *.py

if [ -z "$IS_ACTION" ]; then
  sudo cp dist/readme-runner /usr/local/bin/readme-runner
  exit 0
fi
