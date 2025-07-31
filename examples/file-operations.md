# File Operations Test

This example demonstrates the new file operation tags in docci.

## Create a new HTML file

```html docci-file="example.html" docci-reset-file
<!DOCTYPE html>
<html>
    <head>
        <title>My Titlee</title>
    </head>
    <body>
        <h1>Welcome</h1>
    </body>
</html>
```

## Verify the file was created

```bash docci-output-contains="<!DOCTYPE html>"
cat example.html
```

## Fix the typo in the title (line 4)

```html docci-file="example.html" docci-line-replace="4"
        <title>My Title</title>
```

## Verify the typo was fixed

```bash docci-output-contains="My Title"
grep "title" example.html
```

## Insert content after the h1 tag (line 7)

```html docci-file="example.html" docci-line-insert="7"
        <p>This is a paragraph</p>
        <p>This is another paragraph</p>
```

## Verify the paragraphs were added

```bash docci-output-contains="This is a paragraph"
cat example.html
```

## Create a CSS file

```css docci-file="styles.css"
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
}

h1 {
    color: #333;
}
```

## Add more styles at the end

```css docci-file="styles.css" docci-line-insert="10"

p {
    line-height: 1.6;
    color: #666;
}
```

## Replace the h1 color (line 8)

```css docci-file="styles.css" docci-line-replace="8"
    color: #0066cc;
```

## Verify the final CSS

```bash docci-output-contains="color: #0066cc"
cat styles.css
```

## Test conditional file creation

```bash docci-if-file-not-exists="example.html"
echo "This should not run because example.html exists"
```

## Clean up

```bash
rm -f example.html styles.css
echo "Test files cleaned up"
```
