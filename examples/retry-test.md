# Retry Test Example

This example demonstrates the new `docci-retry` tag functionality.

## Test 1: Command that succeeds on first try

```bash docci-retry=2
echo "This should work on the first attempt"
```

## Test 2: Command that fails and needs retries

```bash docci-retry=2
# This will fail the first few times but eventually succeed
if [ ! -f /tmp/retry_test_counter ]; then
    echo "0" > /tmp/retry_test_counter
fi

counter=$(cat /tmp/retry_test_counter)
counter=$((counter + 1))
echo $counter > /tmp/retry_test_counter

echo "Attempt number: $counter"

if [ $counter -lt 2 ]; then
    echo "Failing on attempt $counter"
    exit 1
else
    echo "Success on attempt $counter!"
    rm -f /tmp/retry_test_counter
fi
```

## Test 3: Using alias for retry

```bash docci-repeat=2
echo "Using the docci-repeat alias"
```

## Test 4: Command that always fails (should fail after max retries)

```bash docci-retry=2 docci-assert-failure
echo "This will always fail"
exit 1
```