# Assert Failure Test

This example demonstrates the `docci-assert-failure` tag which expects code blocks to exit with a non-zero status code.

## Test with non-existent command

This should fail as expected:

```bash docci-assert-failure
# This command doesn't exist and should fail
nonexistentcommand --help
```

## Test with explicit exit 1

This should also fail as expected:

```bash docci-assert-failure
echo "This will print before failing"
exit 1
```

## Normal successful command

This should succeed (no assert-failure tag):

```bash
echo "This command succeeds normally"
```
