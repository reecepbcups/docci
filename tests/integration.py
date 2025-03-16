


import os
import unittest
from typing import Dict, List

from models import Tags


class TestIntegration(unittest.TestCase):
    # TODO; ideally run this like a normal test with parsing.
    # TODO; For now the ````bash is too much of a pain
    def test_readme(self) :
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(curr_dir)
        parent_readme = os.path.join(parent_dir, "README.md")

        with open(parent_readme, 'r') as f:
            content = f.read()

        for dv in manual_parse_content(content):
            # confirm tags are all valid
            headers: str = dv['start'].replace("```bash", "").strip()
            tags = split_outside_quotes(headers)

            tag_validate = Tags.validate(tags)
            if not tag_validate[0]:
                print("Invalid tag found in README.md")
                print(tag_validate[1])
                exit(1)


# this is a really hacky version of parse_markdown_code_blocks
# to just get ```bash and not the ````bash wrappers
def manual_parse_content(content: str) -> List[Dict]:
    # Split content into lines
    lines = content.split("\n")
    results: List[Dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip lines with quadruple backticks
        if "````" in line:
            i += 1
            continue

        # If we find a triple backtick, start collecting content
        if "```" in line:
            start_line = line
            code_content = []
            i += 1  # Move to the next line

            # Collect lines until we find another triple backtick
            while i < len(lines) and "```" not in lines[i]:
                if not lines[i].strip().startswith("#"):
                    code_content.append(lines[i])
                i += 1

            # If we found a closing triple backtick
            if i < len(lines):
                end_line = lines[i]
                results.append({
                    "start": start_line,
                    "content": code_content,
                    "end": end_line
                })

        i += 1

    return results

def split_outside_quotes(text):
    """
    Split a string on spaces that are not between quotes.
    Preserves quoted content as a single argument.

    Args:
        text (str): The input string to split

    Returns:
        list: A list of strings split by spaces outside quotes
    """
    result = []
    current_part = ""
    in_single_quotes = False
    in_double_quotes = False
    i = 0

    while i < len(text):
        char = text[i]

        # Handle quoted sections
        if char == "'" and not in_double_quotes:
            in_single_quotes = not in_single_quotes
            current_part += char
        elif char == '"' and not in_single_quotes:
            in_double_quotes = not in_double_quotes
            current_part += char
        # Handle equals sign with quoted content
        elif char == '=' and i + 1 < len(text) and text[i + 1] in ['"', "'"]:
            # Include the equals sign in the current part
            current_part += char
        # Handle spaces outside quotes
        elif char == ' ' and not in_single_quotes and not in_double_quotes:
            if current_part:  # Don't add empty parts
                result.append(current_part)
                current_part = ""
        else:
            current_part += char

        i += 1

    # Add the last part if it's not empty
    if current_part:
        result.append(current_part)

    return result

if __name__ == '__main__':
    unittest.main()

