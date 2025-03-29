# Source Code Modification

Modifying underlying documents with inserting, replacing, or resetting files.

## Steps

```bash docci-ignore
cd ./examples/3-stdin
```

```bash docci-expected-output="246"
python3 example.py <<< "123"
```

```bash docci-expected-output="246"
VALUE=123
python3 example.py <<< ${VALUE}
```

```bash docci-expected-output="246"
printf "123\n" | python3 example.py
```
