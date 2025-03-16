# Docs CI / Readme Runner

Your documentation is now your test suite!

A CI tool that brings your markdown docs to life by executing code blocks in sequence. Run servers in the background, handle environment variables, add delays, and verify outputs - all through simple markdown tags. Perfect for ensuring your docs stay accurate and your examples actually work!

## Quick Start

### Installation

````bash
make install
````

### Github Actions Integration
````yaml
# make sure to update 1) the version in the URL 2) the config path to run against
- name: Readme Runner
    run: |
    sudo wget -O /usr/local/bin/readme-runner https://github.com/Reecepbcups/docs-ci/releases/download/v0.0.2/readme-runner
    sudo chmod +x /usr/local/bin/readme-runner
    readme-runner .github/workflows/config.json
````

### Usage

````bash
readme-runner <config_path>
````

### Basic Example

````json
{
  "paths": ["docs/README.md"],
  "env_vars": {
    "NODE_ENV": "test"
  },
  "pre_cmds": ["npm install"],
  "cleanup_cmds": ["docker-compose down"],
  "final_output_contains": "Tests passed"
}
````

## Code Block Tags

Control how your documentation code blocks are executed:

````bash
```bash docs-ci-background docs-ci-post-delay=5
# This runs in background and waits 5 seconds after completion
npm start
```
````

## Available tags
 * `docs-ci-ignore`: Skip executing this code block
 * `docs-ci-background`: Run the command in the background
 * `docs-ci-post-delay=N`: Wait N seconds after running commands
 * `docs-ci-cmd-delay=N`: Wait N seconds before each command
 * **TODO:** `docs-ci-wait-for-endpoint=http://localhost:8080/health|N`: Wait up to N seconds for the endpoint to be ready.


---

## How It Works

The tool processes markdown files and executes code blocks based on configuration settings. The core workflow is handled by several key components:

1. **Configuration Loading** (`config_types.py`): Loads and validates the JSON configuration file that specifies paths, environment variables, and commands to run.

2. **Markdown Processing** (`main.py`): Parses markdown files to find executable code blocks and processes them based on their tags.

3. **Command Execution** (`execute.py`): Handles command execution and environment variable substitution.

4. **Tag Processing** (`models.py`): Manages special execution tags that control how code blocks are run.


#### Code Block Tag Examples

Use the ignore tag to skip commands. Useful when you already installed / ran commands in your CI setup.


````bash
```bash docs-ci-ignore
brew install XYZ
```
````
When your command is blocking (like a server you run your CI against), just add the background tag. It also adds a delay after the command starts. Some other setup may take place that we are waiting for but have no way to access yet (unless you want to parse logs output).

````bash
```bash docs-ci-background docs-ci-post-delay=5
cp .env.example .env
make my-long-running-process
# waits 5 seconds here
```
````

Delay all commands by 1 second to give your system time to perform each action without being too fast.

````bash
```bash docs-ci-cmd-delay=1
go run save_large_file.go
cat my-file.txt
```
````


## Configuration Options

- `paths`: List of markdown files or directories to process, in order
- `env_vars`: Environment variables to set during all execution
- `pre_cmds`: Commands to run before processing markdown files
- `cleanup_cmds`: Commands to run after processing
- `final_output_contains`: String that must be present in the final output
