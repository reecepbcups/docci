# Readme Runner 🚀

Your documentation is now your test suite! 🎯

A CI tool that brings your markdown docs to life by executing code blocks in sequence. Run servers in the background, handle environment variables, add delays, and verify outputs - all through simple markdown tags. Perfect for ensuring your docs stay accurate and your examples actually work!

## 🏃‍♂️ Quick Start

### 📦 Installation

````bash
make install
````

### 🤖 Github Actions Integration
````yaml
# make sure to update 1) the version in the URL 2) the config path to run against
- name: Readme Runner
    run: |
    sudo wget -O /usr/local/bin/docs-ci https://github.com/Reecepbcups/docs-ci/releases/download/v0.2.0/docs-ci
    sudo chmod +x /usr/local/bin/docs-ci
    docs-ci .github/workflows/config.json
````

### 🎮 Usage

````bash
docs-ci <config_path>
````

### 📝 Basic Example

````json
{
  "paths": ["docs/README.md"],
  "env_vars": {
    "NODE_ENV": "test"
  },
  "working_dir": "docs/",
  "debugging": false,
  "pre_cmds": ["npm install"],
  "cleanup_cmds": ["docker-compose down"],
}
````

## 🏷️ Code Block Tags

Control how your documentation code blocks are executed:

````bash
```bash docs-ci-background docs-ci-delay-after=5 docs-ci-output-contains="Tests passed"
# This runs in background and waits 5 seconds after completion
npm start
```
````

## 🎨 Available tags
  * 🚫 `docs-ci-ignore`: Skip executing this code block
  * 🚫 `docs-ci-if-not-installed=BINARY`: Skip executing this code block if some binary is installed (e.g. node)
  * 🔄 `docs-ci-background`: Run the command in the background
  * ⏲️ `docs-ci-delay-after=N`: Wait N seconds after running commands
  * ⌛ `docs-ci-delay-per-cmd=N`: Wait N seconds before each command
  * 🌐 `docs-ci-wait-for-endpoint=http://localhost:8080/health|N`: Wait up to N seconds for the endpoint to be ready.
  * 📜 `docs-ci-output-contains="string"`: Ensure the output contains a string at the end of the block

---

## 🛠️ How It Works

The tool processes markdown files and executes code blocks based on configuration settings. The core workflow is handled by several key components:

1. 📋 **Configuration Loading** (`config_types.py`): Loads and validates the JSON configuration file
2. 📝 **Markdown Processing** (`main.py`): Parses markdown files and processes code blocks
3. ⚡ **Command Execution** (`execute.py`): Handles command execution and env vars
4. 🎯 **Tag Processing** (`models.py`): Manages execution control tags


### 💡 Code Block Tag Examples

Skip commands you've already run elsewhere: 🚫

````bash
```bash docs-ci-ignore
brew install XYZ
```
````

````bash
```bash docs-ci-if-not-installed=node
# this only runs if `node` is not found in the system
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
export NVM_DIR="$HOME/.nvm"
nvm install v21.7.3
```
````

Run blocking commands in the background with delays: 🌐

````bash
```bash docs-ci-background docs-ci-delay-after=5
cp .env.example .env
make my-long-running-process
# waits 5 seconds here
```
````

Add delays between commands for stability after the endpoint from a previous command is up: ⏱️

````bash
```bash docs-ci-delay-per-cmd=1 docs-ci-wait-for-endpoint=http://localhost:8080|30
go run save_large_file_from_endpoint.go http://localhost:8080/my-endpoint
# waits 1 second
cat my-file.txt
# waits 1 second
```
````

## ⚙️ JSON Configuration Options

- 📂 `paths`: List of markdown files or directories to process
- 🔐 `env_vars`: Environment variables to set during execution
- 🎬 `pre_cmds`: Commands to run before processing markdown
- 🧹 `cleanup_cmds`: Commands to run after processing
- 📂 `working_dir`: Working directory for command execution
