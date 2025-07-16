# Verbose Background Test

```bash
echo "Starting main execution"
```

```bash docci-background
echo "Background process started"
for i in {1..5}; do
  echo "Background: Processing item $i"
  sleep 0.5
done
echo "Background process completed successfully"
```

```bash
echo "Main process continues..."
sleep 1
echo "Main process finished"
```