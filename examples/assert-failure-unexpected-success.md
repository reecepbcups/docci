# Assert Failure - Unexpected Success Test

This test should FAIL because the code block is marked with `docci-assert-failure` but actually succeeds.

```bash docci-assert-failure
echo "This command succeeds but shouldn't"
echo "Because we marked it with docci-assert-failure"
# This should cause the test to fail because exit code is 0
```