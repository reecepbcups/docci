# Source Code Modification

How to document source code changes into real files for verification.

## Steps

```bash docs-ci-ignore
cd ./examples/2-source-code-impl
```

Create a new file called `example.json` and input the following contents

```json title=example.json docs-ci-insert-at-line=0
{
    "some_key": "My Value"
}
```

```python title=example.py docs-ci-insert-at-line=0
import json

def main():
    with open('example.json', 'r') as f:
        lines = f.readlines()
        data = json.loads(''.join(lines))

    print(data['some_key'])

if __name__ == "__main__":
    main()
```

Run the example, the some_key value is printed. Since this is the last command the output is checked

```bash
python3 example.py
```

The files are then automatically removed after with the config.json
