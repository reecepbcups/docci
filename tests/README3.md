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


```bash
export SOME_OTHER_ENV_VAR=`echo "123456"`
```

```bash docci-output-contains="12345"
echo $SOME_OTHER_ENV_VAR
```

<!-- verify double nested where a $() is wrapped around a `` command -->
```bash
export SOME_OTHER_ENV_VAR=$(echo `echo "ABCDEF"`)
```

```bash docci-output-contains="ABCDEF"
echo $SOME_OTHER_ENV_VAR
```

<!-- Non exported variable -->

```bash docci-output-contains="xyzabc"
SOME_OTHER_ENV_VAR=xyzabc
echo $SOME_OTHER_ENV_VAR
```

<!-- a middle command has the output that is being checked in this block -->

```bash docci-output-contains="456"
echo 123
echo 456
echo 789
```
