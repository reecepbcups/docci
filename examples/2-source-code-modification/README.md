# Source Code Modification

Modifying underlying documents with inserting, replacing, or resetting files.

## Steps

```bash docs-ci-ignore
cd ./examples/2-source-code-modification
```

Create a new file called `example.json` and input the following contents.
- If the file does not exist, it will be created.
- If the file exists, it will be overwritten due to `docs-ci-reset-file`

```json title=example.json docs-ci-reset-file
{
    "some_key": "My Value"
}
```

```python title=example.py docs-ci-reset-file
import json

def main():
    with open('example.json', 'r') as f:
        lines = f.readlines()
        data = json.loads(''.join(lines))

    print(data['some_key'])

if __name__ == "__main__":
    main()
```

Run the example, the `some_key` value is printed & output is verified.

```bash docs-ci-output-contains="My Value"
python3 example.py
```

---

# Replacements and modifications

### Create a new website

```html title=example.html docs-ci-reset-file
<html>
    <head>
        <title>My Titlee</title>
    </head>
</html>
```

### Fix the typo at line 3

```html title=example.html docs-ci-line-replace=3
        <title>My Title</title>
```

### Add new content at line 4

Add main content after the head tag

```html title=example.html docs-ci-line-insert=4
    <body>
        <h1>My Header</h1>
        <p>1 paragraph</p>
        <p>2 paragraph</p>
    </body>
```

### Replace multiple lines

Fix the paragraphs to spell it instead over multiple lines

```html title=example.html docs-ci-line-replace=7-9
        <p>First paragraph</p>
        <p>Second paragraph</p>
```


### Try ot replace non existent lines

If you try to replace a line too far out of bounds, it will just append

```html title=example.html docs-ci-line-replace=44
<!-- example comment at the end of the file -->
```

Negative insert's will wrap around the length, allowing you to append from the end

```html title=example.html docs-ci-line-insert=-1
<!-- Even further comment using -1 as insert -->
```

### Verify it matches expected

Verify against a hardcoded check *(this is just for internal verification)*

```bash
cat example.html | diff - expected.html
```

These files can be automatically removed if your config sets to `rm` in the cleanup section. (regex supported)

```json
{
    "paths": [
      "examples/2-source-code-modification/README.md"
    ],
    "cleanup_cmds": [
      "rm examples/2-source-code-modification/example.py",
      "rm examples/2-source-code-modification/example.json"
      "rm examples/2-source-code-modification/example.html"
    ],
  }
```
