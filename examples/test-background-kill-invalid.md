# Test Invalid Background Kill Reference

This test should fail because it references a non-background block.

## Regular block (index 1)

```bash
echo "This is a regular block at index 1"
```

## Background block (index 2)

```bash docci-background
echo "This is a background block at index 2"
sleep 10
```

## Another regular block (index 3)

```bash
echo "This is a regular block at index 3"
```

## Try to kill a non-background block (should fail)

```bash docci-background-kill="1"
echo "This should not execute"
```
