Starts the service in the background but waits a few seconds before starting. This way the next command would fail if docci-retry was not set.

```bash docci-background
sleep 2 && python3 -m http.server 8000
```

```bash docci-retry=2 docci-output-contains="Directory listing for"
curl http://localhost:8000/
```

<!-- kill python3 -m http.server -->
```bash
kill -9 $(ps aux | grep "[p]ython3 -m http.server 8000" | awk '{print $2}')
```
