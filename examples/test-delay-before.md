# Test Delay Before

This example demonstrates the `docci-delay-before` tag which adds a delay before executing a code block.

## Basic Delay Before

First capture the start time:

```bash
START_TIME=$(date +%s)
echo "Start time: $(date)"
```

Now wait 2 seconds before running the next command:

```bash docci-delay-before="1.5"
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "End time: $(date)"
echo "Elapsed time: $ELAPSED seconds"
if [ $ELAPSED -ge 1 ]; then
    echo "✅ Delay worked correctly (waited at least 1 second)"
else
    echo "❌ Delay did not work (only waited $ELAPSED seconds)"
    exit 1
fi
```
