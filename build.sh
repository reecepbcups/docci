pyinstaller --name readme-runner --workpath __pycache__/build --specpath __pycache__/build/ --onefile *.py

if [ -z "$IS_ACTION" ]; then
  sudo cp dist/readme-runner /usr/local/bin/readme-runner
  exit 0
fi
