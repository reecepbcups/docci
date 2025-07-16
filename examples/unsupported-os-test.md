# Unsupported OS Test

This example demonstrates how unsupported OS values are handled.

## Unsupported OS

This should be skipped because "bsd" is not one of the supported OS types:

```bash docci-os=bsd
echo "This should not run"
exit 1
```

## Normal command that should run

```bash
echo "This should run normally"
```
