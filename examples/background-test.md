# Background Process Test

```bash
echo "Starting regular code block"
```

```bash docci-background
echo "Starting background server..."
echo "Starting background" > $HOME/_tmp_docci_background_test.txt

# Simulate a long-running process, this may exit early (if the foreground processes finish first)
for i in {1..10}; do
  echo "Background process running: $i"
  sleep 1
done
echo "Background process completed"

# clean up if needed (must remain here incase 'background' ever breaks and is not run in parallel)
rm -f $HOME/_tmp_docci_background_test.txt
```

```bash
sleep 0.5

# This checks that the background process is running and has not yet completed (this would happen if the 'background' process blocks)
# checking the file here ensures that the background process has started, is not yet complete, and this is now executing in parallel
if [ ! -f "$HOME/_tmp_docci_background_test.txt" ]; then
  echo "Error: $HOME/_tmp_docci_background_test.txt does not exist"
  exit 1
fi

echo "This runs while background process is active"
sleep 2
echo "Done with foreground work"

# clean up
rm -f $HOME/_tmp_docci_background_test.txt
```
