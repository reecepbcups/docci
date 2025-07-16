# If File Not Exists Test

This example demonstrates the `docci-if-file-not-exists` tag functionality, which only executes code blocks if a specified file doesn't exist.


## Setup
```bash
rm test_example.json backup.txt || true
```

## Basic Usage

The first block will create a config file only if it doesn't already exist:

```bash docci-if-file-not-exists="test_example.json"
echo "Creating config file since it doesn't exist..."
echo '{"version": "1.0", "debug": false}' > test_example.json
echo "Creating backup file..."
echo "backup data" > backup.txt
echo "Config and backup files created!"
```

This second block should be skipped since the config file now exists:

```bash docci-if-file-not-exists="test_example.json"
echo "This should NOT run - test_example.json already exists"
echo "This line should never be executed"
```

## Verification

Let's verify the files were created:

```bash
echo "=== Checking created files ==="
ls -la test_example.json backup.txt
echo ""
echo "=== Config file contents ==="
cat test_example.json
echo ""
echo "=== Backup file contents ==="
cat backup.txt
```

## Cleanup

Remove the created files:

```bash
echo "Cleaning up test files..."
rm -f test_example.json backup.txt
echo "Cleanup complete!"
```

## Testing Edge Cases

Test with a relative path:

```bash docci-if-file-not-exists="./relative_test.txt"
echo "Creating file with relative path..."
echo "test content" > "./relative_test.txt"
```

```bash docci-if-file-not-exists="./relative_test.txt"
echo "This should be skipped - relative path file exists"
```

Cleanup the relative path file:

```bash
rm -f "./relative_test.txt"
echo "Removed relative path file"
```
