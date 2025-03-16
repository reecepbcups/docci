# Node Project Example

## Install Node if not already

yes, technically you can just do this in the github action. Showing how you do in a README.md

```bash docci-if-not-installed=node
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
export NVM_DIR="$HOME/.nvm"
nvm install v21.7.3
```

```bash docci-ignore
cd tests/example1
```

## Install dependencies

```bash docci-delay-after=1
npm i
```

## Build the Binary

```bash
npx tsc
```

```bash docci-background docci-delay-after=1
node dist/app.js
```

```bash docci-output-contains="Hello World!"
curl -X GET http://localhost:3000 --no-progress-meter
```
