# Working Directory Non-existent Path Test

This example demonstrates the `--working-directory` flag with a non-existent path.

To test this, run:
```bash docci-ignore
go run . run --working-directory /nonexistent/path examples/working-directory-nonexistent-test.md
```

Expected behavior: The command should fail with "run directory not found: /nonexistent/path" before any code blocks are executed.

## Test that should never execute

This test should never execute because the working directory validation should fail before any code blocks are processed:

```bash
# This should also never execute
echo "This command should never run"
exit 1
```
