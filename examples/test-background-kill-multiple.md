# Test Multiple Background Process Kill

This example demonstrates killing specific background processes by index.

## Start first background service

```bash docci-background
# Start a simple HTTP server on port 8081
echo "Starting server 1 on port 8081"
python3 -m http.server 8081
```

## Start second background service

```bash docci-background
# Start another HTTP server on port 8082
echo "Starting server 2 on port 8082"
python3 -m http.server 8082
```

## Verify both are running

```bash
echo "Checking both servers..."
curl -s http://localhost:8081 > /dev/null && echo "Server 1 (port 8081) is running"
curl -s http://localhost:8082 > /dev/null && echo "Server 2 (port 8082) is running"
```

## Kill only the first server

```bash docci-background-kill="1"
echo "Killed server 1, waiting for it to stop..."
sleep 1
```

## Verify first is stopped, second still running

```bash
echo "Checking server status after killing server 1..."
if curl -s http://localhost:8081 > /dev/null 2>&1; then
  echo "ERROR: Server 1 is still running!"
else
  echo "SUCCESS: Server 1 has been stopped"
fi

if curl -s http://localhost:8082 > /dev/null 2>&1; then
  echo "SUCCESS: Server 2 is still running"
else
  echo "ERROR: Server 2 was stopped (should still be running)"
fi
```

## Kill the second server

```bash docci-background-kill="2"
echo "Now killing server 2..."
sleep 1
```

## Verify both are stopped

```bash
echo "Final check - both servers should be stopped..."
if curl -s http://localhost:8081 > /dev/null 2>&1; then
  echo "ERROR: Server 1 is running!"
else
  echo "SUCCESS: Server 1 is stopped"
fi

if curl -s http://localhost:8082 > /dev/null 2>&1; then
  echo "ERROR: Server 2 is running!"
else
  echo "SUCCESS: Server 2 is stopped"
fi
```
