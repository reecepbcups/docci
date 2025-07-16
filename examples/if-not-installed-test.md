# Test docci-if-not-installed tag

```bash docci-if-not-installed=ls
# This should not run because ls is already installed
exit 1
```

```bash docci-if-not-installed=nonexistent-fake-command
echo "Installing nonexistent-fake-command..."
echo "This command would install the fake command"
echo "Installation complete!"
```
