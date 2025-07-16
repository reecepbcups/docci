# Multi-block with Assert-Failure Test

This test checks if multiple blocks work correctly when one has assert-failure.

## Block 1: Should succeed
```bash
echo "Block 1 success"
```

## Block 2: Should fail (expected)
```bash docci-assert-failure
echo "Block 2 failing as expected"
exit 1
```

## Block 3: Should not run if Block 2 exits the script
```bash
echo "Block 3 - this should NOT appear if script exits early"
```