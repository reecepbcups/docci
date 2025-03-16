# testing

this is a duplicate of the ../README1.md file to simulate

```
this is ignored
```

```bash docci-output-contains="xyzMyOutput"
echo xyzMyOutput
```

```bash docci-output-contains="abcMyOutput"
echo abcMyOutput
```

```bash docci-assert-failure docci-output-contains="NOT THE RIGHT OUTPUT"
echo abcMyOutput
```


