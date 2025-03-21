import re
import sys
from typing import List, Tuple

from src.config import Config, ScriptingLanguages
from src.managers.cmd import CommandExecutor
from src.managers.core import CodeBlockCore
from src.managers.delay import DelayManager
from src.managers.file_operations import FileOperations
from src.models import Endpoint, Tags, alias_operating_systems


def process_language_parts(language_parts):
    """Process language parts to properly handle quoted values in tags"""
    if len(language_parts) <= 1:
        return []

    raw_tags = language_parts[1:]
    processed_tags = []

    for tag in raw_tags:
        if Tags.TAGS_PREFIX() not in tag: continue
        if '=' in tag: tag = tag.split('=')[0]

        if not Tags.is_valid(tag):
            raise ValueError(f"Invalid tag found in your documentation: {tag}. Check the release notes for renamed tags")

    i = 0
    while i < len(raw_tags):
        current_tag = raw_tags[i]

        # Check if this tag has an opening quote without a closing quote
        if ('="' in current_tag or "='" in current_tag) and not (
            (current_tag.endswith('"') and '="' in current_tag) or
            (current_tag.endswith("'") and "='" in current_tag)
        ):
            # Determine which quote character is used
            quote_char = '"' if '="' in current_tag else "'"

            # Start building the complete tag
            complete_tag = current_tag

            # Keep adding parts until we find the closing quote
            j = i + 1
            while j < len(raw_tags) and quote_char not in raw_tags[j]:
                complete_tag += " " + raw_tags[j]
                j += 1

            # Add the closing part if we found it
            if j < len(raw_tags):
                complete_tag += " " + raw_tags[j]
                i = j  # Skip ahead

            processed_tags.append(complete_tag)
        else:
            processed_tags.append(current_tag)

        i += 1

    return processed_tags

def parse_markdown_code_blocks(config: Config | None, content: str) -> List[CodeBlockCore]:
    """
    Parse a markdown file and extract all code blocks with their language and content.

    Args:
        content: A files contents as a string

    Returns:
        A list of dictionaries, each containing:
        - 'language': The language of the code block
        - 'content': The content of the code block
        - 'should_run': Boolean indicating if this block should be executed (True for bash blocks without docci-ignore)
    """

    # just used internally to remove outer code blocks which show nicely in markdown.
    # also useful for anyone else who does this
    if '````' in content:
        modified = ""
        for i, line in enumerate(content.split('\n')):
            does_contain_4_backticks = '````' in line
            if does_contain_4_backticks:
                next_line = content.split('\n')[i + 1]
                prev_line = content.split('\n')[i - 1] if i > 0 else ""
                if '```' in next_line:
                    continue
                elif '```' in prev_line:
                    continue
                else:
                    modified += line + '\n'
            else:
                modified += line + '\n'
        content = modified if modified else content

    # Regex pattern to match code blocks: ```language ... ```
    # Capturing groups:
    # 1. Language and any additional markers (e.g., 'bash docci-ignore')
    # 2. Content of the code block
    pattern = r'```(.*?)\n(.*?)```'

    # Find all matches with re.DOTALL to include newlines
    matches = re.findall(pattern, content, re.DOTALL)

    results: List[CodeBlockCore] = []
    for language_info, block_content in matches:
        language_info = language_info.strip()
        language_parts = language_info.split()

        # Get the primary language
        language = language_parts[0] if language_parts else ''
        tags = process_language_parts(language_parts) if len(language_parts) > 0 else []

        ignored = Tags.IGNORE() in tags
        if config is not None:
            ignored = ignored or language not in config.followed_languages

        # we can not strip content if it's language based, only for scripts
        content = str(block_content)
        if language in ScriptingLanguages:
            content = content.strip()

        # Create file operations if any file-related tags are present
        file_ops = FileOperations(
            file_name=Tags.extract_tag_value(tags, Tags.FILE_NAME(), default=None),
            content=content,
            insert_at_line=Tags.extract_tag_value(tags, Tags.INSERT_AT_LINE(), default=None, converter=int),
            replace_lines=Tags.extract_tag_value(tags, Tags.REPLACE_AT_LINE(), default=None, converter=replace_at_line_converter),
            file_reset=Tags.has_tag(tags, Tags.RESET_FILE),
            if_file_not_exists=Tags.extract_tag_value(tags, Tags.IF_FILE_DOES_NOT_EXISTS(), default="")
        )

        # Create delay manager
        delay_manager = DelayManager(
            post_delay=Tags.extract_tag_value(tags, Tags.POST_DELAY(), default=0, converter=int),
            cmd_delay=Tags.extract_tag_value(tags, Tags.CMD_DELAY(), default=0, converter=int)
        )

        # using regex, remove any sections of code that start with a comment '#' and end with a new line '\n', this info is not needed.
        # an example is '# Install packages (npm & submodules)\nmake setup\n\n# Build the contracts\nforge build\n\n# Run the solidity tests\nforge test'
        # this should just be `make setup\nforge build\nforge test`
        content = re.sub(r'^#.*\n', '', content, flags=re.MULTILINE)
        # if there is a # comment with no further \n after it, remove it
        content = re.sub(r'#.*$', '', content, flags=re.MULTILINE).strip()
        # ensure only 1 \n is present, not ever \n\n or more
        content = re.sub(r'\n+', '\n', content)
        # split by the \n to get a list of commands
        commands = content.split('\n')

        # Create command executor if any command-related tags are present
        command_executor = None
        if language in ScriptingLanguages:
            command_executor = CommandExecutor(
                commands=commands,
                background=Tags.has_tag(tags, Tags.BACKGROUND),
                output_contains=Tags.extract_tag_value(tags, Tags.OUTPUT_CONTAINS(), default=None),
                expect_failure=Tags.has_tag(tags, Tags.ASSERT_FAILURE),
                machine_os=(Tags.extract_tag_value(tags, Tags.MACHINE_OS(), default=None, converter=alias_operating_systems) or None),
                binary=Tags.extract_tag_value(tags, Tags.IGNORE_IF_INSTALLED(), default=None),
                ignored=ignored,
                delay_manager=delay_manager,
                if_file_not_exists=Tags.extract_tag_value(tags, Tags.IF_FILE_DOES_NOT_EXISTS(), default="") # TODO: remove from the other type?
            )

        value = CodeBlockCore(
            language=language,
            tags=tags,
            content=content,
            ignored=ignored,
            delay_manager=delay_manager,
            file_ops=file_ops,
            command_executor=command_executor,
            endpoint=Endpoint.handle_http_polling_input(Tags.extract_tag_value(tags, Tags.HTTP_POLLING(), default=None)),
        )
        results.append(value)

    return results

# input could be just a number ex: 3, or a range of numbers; 2-4
def replace_at_line_converter(value: str) -> Tuple[int, int | None]:
    if '-' in value:
        start, end = value.split('-')
        return int(start), int(end)
    return int(value), None
