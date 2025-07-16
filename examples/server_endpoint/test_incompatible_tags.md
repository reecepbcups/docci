# Test Incompatible Tag Combinations

This test should fail because docci-wait-for-endpoint and docci-background cannot be used together:

```bash docci-wait-for-endpoint="http://localhost:8080/health|10" docci-background
echo "This should not work"
```