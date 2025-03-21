#!/usr/bin/env -S python3 -B

import inspect
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

from config import Config, ScriptingLanguages
from execute import parse_env
from models import Endpoint, Tags, alias_operating_systems, handle_http_polling_input
from src.managers.delay import DelayManager
from src.processes_manager import process_manager


def main():
    """Main entry point for the application."""
    # Parse command-line arguments
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config_path|config_json_blob> [--tags]")
        sys.exit(1)

    if "--tags" in sys.argv:
        Tags.print_tags_with_aliases()
        sys.exit(0)

    cfg_input = sys.argv[1]

    # Load configuration
    try:
        config = Config.load_configuration(cfg_input)
    except Exception as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # Run the documentation processor
    error = run_documentation(config)
    if error:
        print(f"Error: {error}")
        sys.exit(1)

    print("Documentation processing completed successfully.")

def run_documentation(config: Config) -> Optional[str]:
    """
    Execute documentation code blocks according to configuration.

    Args:
        config: The loaded configuration

    Returns:
        Error message or None if successful
    """
    try:
        # Set up environment
        config.run_pre_cmds(hide_output=True)
        for key, value in config.env_vars.items():
            os.environ[key] = value

        # Process all content paths
        for parent_path_key, file_paths in config.get_all_possible_paths().items():
            try:
                for file_path in file_paths:
                    # Read and parse file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Extract and process code blocks
                    code_blocks = parse_markdown_code_blocks(config, content)

                    # Execute commands for each code block
                    for i, block in enumerate(code_blocks):
                        error = block.run_commands(config=config)
                        if error:
                            return f"Error({parent_path_key},{file_paths}): {error}"

            except KeyboardInterrupt:
                print("\nKeyboardInterrupt: Quitting...")
                return "Interrupted by user"
            except Exception as e:
                return f"Error({parent_path_key},{file_paths}): {e}"

    except Exception as e:
        return f"Setup error: {e}"
    finally:
        # Always clean up resources
        process_manager.cleanup()
        config.run_cleanup_cmds(hide_output=True)

    return None



@dataclass
class FileOperations:
    file_name: Optional[str] = None
    content: str = ""
    insert_at_line: Optional[int] = None
    replace_lines: Optional[Tuple[int, Optional[int]]] = None
    file_reset: bool = False
    if_file_not_exists: str = ""

    def handle_file_content(self, config: Config) -> bool:
        if not self.file_name:
            return False

        file_path = os.path.join(config.working_dir, self.file_name) if config.working_dir else self.file_name

        # Check if_file_not_exists condition
        if self.if_file_not_exists and os.path.exists(file_path):
            if config.debugging:
                print(f"Skipping file operation since {file_path} exists and if_file_not_exists is set")
            return False

        # Ensure content ends with newline for proper line operations
        content_with_newline = self.content if self.content.endswith('\n') else self.content + '\n'

        if not os.path.exists(file_path) or self.file_reset:
            if config.debugging:
                print(f"Refreshing file: {file_path}", "since file reset is on" if self.file_reset else "")
            with open(file_path, 'w') as f:
                f.write(content_with_newline)

        # read and insert at the given line
        with open(file_path, 'r') as f:
            lines = f.readlines()

        if self.insert_at_line:
            # if insert at line is negative, then it is relative to the end of the file
            insert_line = self.insert_at_line if self.insert_at_line > 0 else len(lines) + self.insert_at_line + 1
            # Ensure we don't go out of bounds
            insert_line = max(0, min(insert_line, len(lines)))
            lines.insert(insert_line, content_with_newline)

        if self.replace_lines:
            start, end = self.replace_lines
            # line based, not index :)
            start = start - 1 if start > 0 else 0
            end = end - 1 if end and end > 0 else None

            if end:
                if end >= len(lines):
                    end = len(lines)
                lines[start:end] = [content_with_newline]
            else:
                if start >= len(lines):
                    lines.append(content_with_newline)
                else:
                    lines[start] = content_with_newline

        with open(file_path, 'w') as f:
            f.write(''.join(lines))

        return True



@dataclass
class CommandExecutor:
    commands: List[str]
    background: bool = False
    output_contains: Optional[str] = None
    expect_failure: bool = False
    machine_os: Optional[str] = None
    binary: Optional[str] = None
    ignored: bool = False
    delay_manager: Optional[DelayManager] = None
    if_file_not_exists: str = ""

    def run_commands(
        self,
        config: Config,
        background_exclude_commands: List[str] = ["cp", "export", "cd", "mkdir", "echo", "cat"],
    ) -> str | None:
        if self.ignored:
            if config.debugging:
                print(f"Ignoring commands...")
            return None

        # Check if file exists when if_file_not_exists is set
        if self.if_file_not_exists:
            file_path = os.path.join(config.working_dir, self.if_file_not_exists) if config.working_dir else self.if_file_not_exists
            if os.path.exists(file_path):
                if config.debugging:
                    print(f"Skipping commands since {file_path} exists")
                return None

        system = platform.system().lower()
        if self.machine_os and self.machine_os != system:
            if config.debugging:
                print(f"Skipping command since it is not for the current OS: {self.machine_os}, current: {system}")
            return None

        if self.binary and shutil.which(self.binary):
            print(f"Skipping command since {self.binary} is already installed.")
            return None

        env = os.environ.copy()
        response = None
        had_error = False

        for command in self.commands:
            if command in config.ignore_commands:
                continue

            env.update(parse_env(command))
            cmd_background = self._should_run_in_background(command, background_exclude_commands)

            if cmd_background and not command.strip().endswith('&'):
                command = f"{command} &"

            if config.debugging:
                print(f"Running command: {command}" + (" (& added for background)" if cmd_background else ""))

            if self.delay_manager:
                self.delay_manager.handle_delay("cmd")

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE if self.output_contains else None,
                stderr=subprocess.PIPE if self.output_contains else None,
                shell=True,
                env=env,
                cwd=config.working_dir,
                text=False,
            )

            if cmd_background:
                if process.pid:
                    process_manager.add_process(process.pid)
            else:
                if self.output_contains:
                    stdout, stderr = process.communicate()
                    output = ""

                    if stdout:
                        sys.stdout.buffer.write(stdout)
                        sys.stdout.flush()
                        output += stdout.decode('utf-8', errors='replace')

                    if stderr:
                        sys.stderr.buffer.write(stderr)
                        sys.stderr.flush()
                        err = stderr.decode('utf-8', errors='replace')
                        output += err
                        if err:
                            had_error = True

                    if self.commands[-1] == command and self.output_contains not in output:
                        response = f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
                        break
                    else:
                        if config.debugging:
                            print(f"Output contains: {self.output_contains}")
                else:
                    process.wait()
                    if process.returncode != 0:
                        response = f"Error running command: {command}"
                        break

        if self.delay_manager:
            self.delay_manager.handle_delay("post")

        if self.expect_failure:
            if had_error:
                return None
            else:
                return "Error: expected failure but command succeeded"

        return response

    def _should_run_in_background(self, command: str, exclude_commands: List[str]) -> bool:
        if not self.background:
            return False
        first_word = command.strip().split()[0]
        return first_word not in exclude_commands

@dataclass
class DocsValue:
    language: str
    tags: List[str]
    content: str
    ignored: bool
    delay_manager: DelayManager
    file_ops: Optional[FileOperations] = None
    command_executor: Optional[CommandExecutor] = None
    endpoint: Optional[Endpoint] = None

    def run_commands(self, config: Config) -> str | None:
        if self.endpoint:
            print(f"waiting for endpoint: {self.endpoint}")
            lastRes = (False, "")
            for res in self.endpoint.poll(poll_speed=1):
                lastRes = res
            if not lastRes[0]:
                return f"Error: endpoint not up in timeout period: {self.endpoint.url}"

        if self.file_ops and self.file_ops.handle_file_content(config):
            return None

        if self.command_executor:
            response = self.command_executor.run_commands(config)
            if response and self.command_executor.expect_failure:
                return None
            elif not response and self.command_executor.expect_failure:
                return "Error: expected failure but command succeeded"
            return response

        return None

    def __str__(self):
        return f"DocsValue(language={self.language}, tags={self.tags}, ignored={self.ignored}, delay_manager={self.delay_manager})"

    def print(self):
        print(self.__str__())


# def extract_tag_value(tags, tag_type, default=None, converter=None):
#     """
#     Extract value from a tag of format 'tag_type=value' or 'tag_type="value with spaces"'
#     """
#     matching_tags = []

#     for tag in tags:
#         if tag_type in tag:
#             # Find the position of the equals sign
#             equals_pos = tag.find('=')
#             if equals_pos != -1:
#                 # Get everything after the equals sign
#                 value = tag[equals_pos + 1:]

#                 # Check if the value starts with a quote
#                 if value and (value[0] == '"' or value[0] == "'"):
#                     quote_char = value[0]
#                     # Look for the matching closing quote
#                     for i in range(1, len(value)):
#                         if value[i] == quote_char:
#                             # Extract the value WITHOUT quotes
#                             value = value[1:i]
#                             break
#                 else:
#                     # No quotes, just use the value as is
#                     value = value

#                 matching_tags.append(value)

#     if not matching_tags:
#         return default

#     value = matching_tags[0]
#     return converter(value) if converter else value

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

def parse_markdown_code_blocks(config: Config | None, content: str) -> List[DocsValue]:
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

    # Regex pattern to match code blocks: ```language ... ```
    # Capturing groups:
    # 1. Language and any additional markers (e.g., 'bash docci-ignore')
    # 2. Content of the code block
    pattern = r'```(.*?)\n(.*?)```'

    # Find all matches with re.DOTALL to include newlines
    matches = re.findall(pattern, content, re.DOTALL)

    results: List[DocsValue] = []
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
        # TODO: other comment types need to also be supported?
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

        value = DocsValue(
            language=language,
            tags=tags,
            content=content,
            ignored=ignored,
            delay_manager=delay_manager,
            file_ops=file_ops,
            command_executor=command_executor,
            endpoint=handle_http_polling_input(Tags.extract_tag_value(tags, Tags.HTTP_POLLING(), default=None)),
        )
        results.append(value)

    return results
# input could be just a number ex: 3
# or a range of numbers; 2-4
def replace_at_line_converter(value: str) -> Tuple[int, int | None]:
    if '-' in value:
        start, end = value.split('-')
        return int(start), int(end)
    return int(value), None

if __name__ == "__main__":
    main()
