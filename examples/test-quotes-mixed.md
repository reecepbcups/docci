# Test Mixed Quote Cases

Test various quote combinations:

```bash docci-output-contains='"operators": []'
echo '{"operators": [], "test": "value"}'
```

```bash docci-output-contains="simple text"
echo "This is simple text without quotes"
```

```bash docci-output-contains='text with "quotes" inside'
echo 'Here is text with "quotes" inside it'
```
