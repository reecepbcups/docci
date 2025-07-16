# Working Directory Relative Path Test

This example demonstrates the `--working-directory` flag with a relative path.

To run this test properly, use the following command from the docci root directory:
```bash docci-ignore
go run . run --working-directory examples $(pwd)/examples/working-directory-relative-test.md
```

## Test working directory functionality

This test shows basic working directory functionality:

```bash
echo "Current working directory: $(pwd)"
```

```bash
# Show the current directory name  
basename $(pwd)
```

## Test file access in current directory

This test verifies that we can access files in the current working directory:

```bash
# Test that we can list files in the current directory
ls -la | head -5
```

```bash docci-output-contains="Working directory test completed"
# Simple completion message
echo "Working directory test completed successfully"
```