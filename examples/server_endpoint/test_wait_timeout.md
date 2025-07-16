# Test Wait for Endpoint Timeout

This test demonstrates that the `docci-wait-for-endpoint` functionality correctly times out when an endpoint is not available.

## Test Timeout Behavior

This should timeout after 1 second since no server is running on port 9999:

```bash docci-wait-for-endpoint="http://localhost:9999/health|1"
echo "This should not be reached"
```