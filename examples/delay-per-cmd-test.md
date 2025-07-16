# Delay Per Command Test

This example demonstrates the `docci-delay-per-cmd` functionality that adds a delay between each command execution.

## Basic Usage

The `docci-delay-per-cmd` tag adds a specified delay (in seconds) between each command in a code block:

```bash docci-delay-per-cmd=1 docci-output-contains="SUCCESS: Timestamps are different"
TIME1=$(date +%H:%M:%S)
TIME2=$(date +%H:%M:%S)

# shows complex bash structures work as well
if [ "$TIME1" != "$TIME2" ]; then
    echo "SUCCESS: Timestamps are different ($TIME1 vs $TIME2)"
else
    echo "FAIL: Timestamps are the same"
    exit 1
fi
```
