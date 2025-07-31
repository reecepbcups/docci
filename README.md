# Docci | Readme Test 🚀 &middot; [![GitHub license](https://img.shields.io/badge/license-apache-blue.svg)](https://github.com/Reecepbcups/docci/blob/main/LICENSE) [![Tests](https://github.com/Reecepbcups/docci/actions/workflows/go-unit-test.yml/badge.svg)](https://github.com/Reecepbcups/docci/actions/workflows/test.yml) [![Compatible](https://img.shields.io/badge/compatible%20-macOS_&_linux-8A2BE2.svg)](https://github.com/Reecepbcups/docci)

Your documentation is now your test suite! 🎯 *(pronounced "doc-ee", short for documentation CI)*

A CI tool that brings your markdown docs to life by executing code blocks in sequence. Run processes in the background, handle environment variables, add delays, verify outputs, and modify files - all through simple markdown tags. Perfect for ensuring your docs stay accurate and your examples actually work! 📚

## 🌟 Projects Using Docci

Several projects have adopted Docci to ensure their documentation stays accurate and executable:

- **[Spawn](https://github.com/rollchains/spawn)** - Rapid Cosmos blockchain development framework
- **[WAVS](https://github.com/Lay3rLabs/wavs-middleware)** - Eigenlayer AVS WebAssembly development
- **[OndoChain](https://blog.ondo.finance/introducing-ondo-chain/)** - Institutional RWA Cosmos-EVM blockchain

## 🏃‍♂️ Quick Start

Find sample workspaces in the [`examples/` directory](./examples/).

### 📦 Installation

[Go `1.23`+](https://go.dev/doc/install) is required. You can also download a pre-built binary from the [release page](https://github.com/Reecepbcups/docci/releases).

```bash docci-ignore
go install github.com/reecepbcups/docci
```

```bash docci-ignore
git clone git@github.com:Reecepbcups/docci.git --depth 1
cd docci
go mod tidy
task install # go install ./*.go
```

### 🤖 Github Actions Integration
````yaml
  # docci_Linux_x86_64, docci_Linux_arm64, docci_Darwin_x86_64, docci_Darwin_arm64
  - name: Install Docci Readme Test Tool
    run: |
      VERSION=v0.9.2
      BINARY=docci_Linux_x86_64.tar.gz
      curl -fsSL "https://github.com/Reecepbcups/docci/releases/download/${VERSION}/${BINARY}" | sudo tar -xzC /usr/local/bin
      sudo chmod +x /usr/local/bin/docci

  - run: docci run YOUR_MARKDOWN_FILE.md --hide-background-logs
````

### 🎮 Usage

```bash docci-ignore
docci run <markdown_file.md> [options]

docci run nested/README.md --hide-background-logs
docci run A.md --cleanup-commands "docker-compose down" --cleanup-commands "rm -rf /tmp/test"
docci run A.md --pre-commands "npm install"

docci tags

docci version
```

### 🎨 Operation tags
  * 🛑 `docci-ignore`: Skip executing this code block
  * 🔄 `docci-background`: Run the command in the background
  * 💀 `docci-background-kill=N`: Kill a previously started background process by index (1-based)
  * 🚫 `docci-if-not-installed=BINARY`: Skip execution if some binary is installed (e.g. node)
  * ⏲️ `docci-delay-before=N`: Wait N seconds before running any commands in the block
  * ⏲️ `docci-delay-after=N`: Wait N seconds after running all commands in the block
  * ⌛ `docci-delay-per-cmd=N`: Wait N seconds before each command
  * ⏲️ `docci-retry=N`: Retry command N times *(pair with docci-delay-per-cmd)*
  * 🌐 `docci-wait-for-endpoint=http://localhost:8080/health|N`: Wait up to N seconds for the endpoint to be ready
  * 📜 `docci-output-contains="string"`: Ensure the output contains a string at the end of the block (also use `=''`)
  * 🚨 `docci-assert-failure`: If it is expected to fail (non 0 exit code)
  * 🖥️ `docci-os=mac|linux`: Run the command only on it's the specified OS
  * 🔄 `docci-replace-text="old;new"`: Replace text in the code block before execution (including env variables!)

### 📄 File Tags
  * 📝 `docci-file`: The file name to operate on
  * 🔄 `docci-reset-file`: Reset the file to its original content
  * 🚫 `docci-if-file-not-exists`: Only run if a file does not exist
  * ➕ `docci-line-insert=N`: Insert content at line N
  * ✏️ `docci-line-replace=N`: Replace content at line N
  * 📋 `docci-line-replace=N-M`: Replace content from line N to M


### 💡 Code Block Tag Examples (Operations)

Skip needless installations if you are already set up: 🛑

<!-- The 4 backticks is just so it wraps in githubs UI, real test are written normally with the nested part (just 3 backticks) -->
````bash
```bash docci-os=linux docci-if-not-installed=node
# this only runs if `node` is not found in the system & it's a linux system
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
export NVM_DIR="$HOME/.nvm"
nvm install v21.7.3
```
````

Ensure the output (stdout or stderr) contains a specific string: 📜

````bash
```bash docci-contains="xyzMyOutput"
echo xyzMyOutput
```
````

Run blocking commands in the background: 🌐

````bash
```bash docci-background docci-delay-after=2
go run examples/server_endpoint/test_server.go 3000
```
````

Add delays between commands for stability after the endpoint from a previous command is up: ⏱️

````bash
```bash docci-output-contains="GOOD" docci-wait-for-endpoint=http://localhost:3000/health|30
VALUE=$(curl http://localhost:3000/health)
echo "Got value: $VALUE"
```
````


Assert that a command fails: 🚨

````bash
```bash docci-assert-failure
notinstalledbin --version
```
````

Set ENV Variables

````bash
```bash
export SOME_ENV_VAR="abcdef"
OTHER_ENV_VAR="ghijkl"
echo "SOME_ENV_VAR is $SOME_ENV_VAR and OTHER_ENV_VAR is $OTHER_ENV_VAR"
```
````

Replace text before execution (useful for CI/CD): 🔄

````bash
```bash docci-replace-text="API_KEY;$SOME_ENV_VAR"
echo "Imagine a cURL request with API_KEY here"
```
````

Cleanup demo server if running in the background:

````bash
```bash
curl http://localhost:3000/kill
```
````

### 💡 Files Code Block Tag Examples

Create a new file from content: 📝

<!-- yes, the typo is meant to be here -->
````html
```html docci-file=example.html docci-reset-file
<html>
    <head>
        <title>My Titlee</title>
    </head>
</html>
```
````

Replace the typo'ed line:

````html
```html docci-file=example.html docci-line-replace=3
        <title>My Title</title>
```
````

Add new content

````html
```html docci-file=example.html docci-line-insert=4
    <body>
        <h1>My Header</h1>
        <p>1 paragraph</p>
        <p>2 paragraph</p>
    </body>
```
````

Replace multiple lines

````html
```html docci-file=example.html docci-line-replace=7-9
        <p>First paragraph</p>
        <p>Second paragraph</p>
```
````
