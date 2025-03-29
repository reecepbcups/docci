
## Persisted env vars across blocks
```bash
DOCCI_MISC_ENV_VAR=1
```

```bash docci-output-contains="1"
echo $DOCCI_MISC_ENV_VAR
```
