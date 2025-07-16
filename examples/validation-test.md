# Validation Test

```bash
echo "Hello World"
```

```bash docci-output-contains="test value"
VAR="test value"
echo "This contains $VAR"
```

```bash docci-output-contains="Success"
echo "Success: All tests passed!"
```
