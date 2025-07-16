# OS-Specific Code Blocks Test

This example demonstrates the `docci-os` and `docci-machine` tags for OS-specific execution.

## Linux-only commands

This should run on Linux systems only:

```bash docci-os=linux
echo "This is running on Linux!"
uname -s
```

## macOS-only commands

This should run on macOS systems only:

```bash docci-os=macos
echo "This is running on macOS!"
sw_vers
```

## Windows-only commands

This should run on Windows systems only:

```bash docci-os=windows
echo "This is running on Windows!"
ver
```

## Using the alias docci-machine

This should also work with the alias:

```bash docci-machine=linux
echo "Using docci-machine alias for Linux"
```

## No OS restriction

This should run on any supported OS:

```bash
echo "This runs on any OS"
echo "Current working directory: $(pwd)"
```