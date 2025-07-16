# Example Markdown

```
This is ignored
```

Here is some other text

```bash
echo "This is a bash command"
sleep 0.1
echo "other text"
```

```shell docci-ignore
echo "This is ignored"
```

```sh
VAR="test"
echo "This is a bash command with a variable: $VAR"
```

```go
// incorrect language specified
func main() {
    fmt.Println("Hello, World!")
}
```

```bash docci-output-contains="Persist test"
# ensure VAR is set, if not exit 1
if [ -z "$VAR" ]; then
  echo "VAR is not set, exiting"
  exit 1
fi

echo "Persist $VAR"
```
