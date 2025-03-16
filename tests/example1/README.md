
## Install Node if not already

yes, technically you can just do this in the github action. Showing how you do in a README.md

```bash
if [ ! command -v node &> /dev/null ]; then
    echo "NodeJS not found, installing via NVM"
    # curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
    # export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
    # nvm install v21.7.3
fi
```

## Install dependencies

```bash
npm i
```

## Build the Binary

```bash
npx tsc
```

```bash docs-ci-background
node dist/app.js
```

```bash
curl -X GET http://localhost:3000
```
