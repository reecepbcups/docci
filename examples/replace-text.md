# Replace Text Tag Test

## Basic

```bash docci-output-contains="Value is: 42" docci-replace-text="PLACEHOLDER;42"
echo "Value is: PLACEHOLDER"
```

## Multiple Occurrences

```bash docci-replace-text="XXX;YYY"
echo "XXX appears here"
echo "And XXX appears here too"
echo "Even XXX appears a third time"
```

```bash
# imagine this was set in the CI env with github action secrets.
MY_SECRET_ENV_VAR="secret123"
```

## Replacement with an Environment Variable

```bash docci-output-contains="secret123" docci-replace-text="SECRET_HERE;$MY_SECRET_ENV_VAR"
echo "SECRET_HERE"
```

## Replacement with the ; in the command

Complex replacement that puts multiple commands in 1 command, keeping the original

```bash docci-output-contains="xyz" docci-replace-text="abc;echo abc;echo xyz"
echo "abc"
```
