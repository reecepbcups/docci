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
from typing import Dict, Generator, List, Literal, Optional, Tuple

import requests

from config_types import Config, ScriptingLanguages
from execute import execute_substitution_commands
from models import Endpoint, Tags, alias_operating_systems, handle_http_polling_input

# Store PIDs of background processes for later cleanup
background_processes = []

# do_logic returns an error if it fails
def do_logic(config: Config) -> str | None:
    config.run_pre_cmds(hide_output=True)
    for key, value in config.env_vars.items():
        os.environ[key] = value

    for parentPathKey, file_paths in config.get_all_possible_paths().items():
        try:
            for file_path in file_paths:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                values = parse_markdown_code_blocks(config, content)
                # if config.debugging: print(f"Values: {values}")

                for i, value in enumerate(values):
                    err = value.run_commands(config=config)
                    if err:
                        return f"Error({parentPathKey},{file_paths}): {err}"
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt: Quitting...")
        except Exception as e:
            return f"Error({parentPathKey},{file_paths}): {e}"
        finally:
            cleanup_background_processes()
            config.run_cleanup_cmds(hide_output=True)

    return None

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config_path|config_json_blob>")
        sys.exit(1)

    cfg_input = sys.argv[1]

    if os.path.isdir(cfg_input):
        # TODO: search through all json files in dir & find ones content whose matches the expected layout
        cfg_input = os.path.join(cfg_input, 'config.json')
        if not os.path.exists(cfg_input):
            print(f"Error: config.json not found in directory: {sys.argv[1]}")
            sys.exit(1)

    if os.path.isfile(cfg_input):
        config: Config = Config.load_from_file(cfg_input)
    else:
        config: Config
        try:
            config = Config.from_json(json.loads(cfg_input))
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON input: {e}. Make sure the JSON is valid or the path is correct")
            sys.exit(1)

    err = do_logic(config)
    if err:
        print(err)
        sys.exit(1)

@dataclass
class DocsValue:
    language: str # bash, python, rust, etc
    tags: List[str] # (e.g., 'docci-ignore') in the ```bash tag1, tag2```
    content: str # unmodified content
    ignored: bool
    commands: List[str]
    background: bool = False # if the command should run in the background i.e. it is blocking
    post_delay: int = 0 # delay in seconds after the command is run
    cmd_delay: int = 0 # delay in seconds before each command is run
    wait_for_endpoint: Optional[Endpoint] = None
    binary: Optional[str] = None
    output_contains: Optional[str] = None
    expect_failure: bool = False
    machine_os: Optional[str] = None
    # Files: it will create if it does not exist.
    # when the file does, it will insert the content at the line number. if the file is empty, it will always insert at the start (idx 0)
    file_name: Optional[str] = None
    insert_at_line: Optional[int] = None
    replace_lines: Optional[Tuple[int, Optional[int]]] = None # start and optional end
    file_reset: bool = False

    # returns a string or bool. if bool is true, success, if false, failed
    def endpoint_poll_if_applicable(self, poll_speed: float = 1.0) -> Generator[Tuple[bool, str], None, None]:
        start_time = time.time()
        attempt = 1
        url = self.wait_for_endpoint.url
        while True:
            try:
                requests.get(url)
                yield True, f"Success: endpoint is up: {url}"
                break
            except requests.exceptions.RequestException:
                if time.time() - start_time > self.wait_for_endpoint.max_timeout: # half second buffer
                    break
                yield False, f"Error: endpoint not up yet: {url}, trying again. Try number: {attempt}"
                time.sleep(poll_speed)
            attempt += 1

    # handle_file_content returns True if we handled a file, False if we did not
    # NOTE: we handle this as a human reads it, lines start at ONE (1), not zero
    def handle_file_content(self, config: Config) -> bool:
        if not self.file_name:
            return False

        file_path = os.path.join(config.working_dir, self.file_name) if config.working_dir else self.file_name

        if not os.path.exists(file_path) or self.file_reset:
            if config.debugging:
                print(f"Refreshing file: {file_path}", "since file reset is on" if self.file_reset else "")
            with open(file_path, 'w') as f:
                f.write(self.content)

        # read and insert at the given line
        with open(file_path, 'r') as f:
            lines = f.readlines()

        if self.insert_at_line:
            # if insert at line is negative, then it is relative to the end of the file
            insert_line = self.insert_at_line if self.insert_at_line > 0 else len(lines) + self.insert_at_line + 1
            lines.insert(insert_line, self.content)

        if self.replace_lines:
            start, end = self.replace_lines
            # line based, not index :)
            start = start - 1 if start > 0 else 0
            end = end - 1 if end and end > 0 else None
            if end:
                if end > len(lines):
                    end = len(lines) - 1

                lines[start:end] = self.content
            else:
                if start > len(lines):
                    lines.append(self.content)
                else:
                    lines[start] = self.content

        with open(file_path, 'w') as f:
            f.write(''.join(lines))

        return True

    def run_commands(
        self,
        config: Config,
        background_exclude_commands: List[str] = ["cp", "export", "cd", "mkdir", "echo", "cat"],
    ) -> str | None:
        '''
        Runs the commands. host env vars are pulled into the processes

        returns: error message if any
        '''

        env = os.environ.copy()

        response = None # success

        if self.binary:
            if shutil.which(self.binary):
                print(f"Skipping command since {self.binary} is already installed.")
                return None

        if self.wait_for_endpoint:
            lastRes: Tuple[bool, str] = (False, "")
            for res in self.endpoint_poll_if_applicable(poll_speed=1):
                lastRes = res

            print(lastRes)
            if lastRes[0] == False:
                print(lastRes[1])
                return f"Error: endpoint not up in timeout period: {self.wait_for_endpoint.url}"

        if self.handle_file_content(config):
            return None

        if self.ignored:
            if config.debugging:
                c = self.content.replace('\n', '\\n').replace('    ', '\\t')
                print(f"Ignoring commands for {self.language}... ({c})")
            return None

        system = platform.system().lower() # linux (wsl included), darwin (mac), windows
        if self.machine_os and self.machine_os != system:
            if config.debugging:
                print(f"Skipping command since it is not for the current OS: {self.machine_os}, current: {system}")
            return None


        for command in self.commands:
            if command in config.ignore_commands:
                continue

            # parse out env vars from commands. an example format is:
            # --> export SERVICE_MANAGER_ADDR=`make get-eigen-service-manager-from-deploy
            # this should be done here as it is more JIT, can't do earlier else other are not ready
            env.update(parse_env(command))

            # Determine if this specific command should run in background
            cmd_background = self.background
            if self.background:
                # Check if command starts with any excluded prefix
                first_word = command.strip().split()[0]
                if first_word in background_exclude_commands:
                    cmd_background = False

            # Add & if running in background and not already there
            if cmd_background and not command.strip().endswith('&'):
                command = f"{command} &"

            if config.debugging:
                print(f"Running command: {command}" + (" (& added for background)" if cmd_background else ""))

            if self.cmd_delay > 0:
                print(f"Sleeping for {self.cmd_delay} seconds before running command (cmd-delay)...")
                for i in range(self.cmd_delay, 0, -1):
                    print(f"Sleep: {i} seconds remaining...")
                    time.sleep(1)

            process = process = subprocess.Popen(
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
                    background_processes.append(process.pid)
            else:
                if self.output_contains:
                    stdout, stderr = process.communicate()
                    output = ""

                    if stdout:
                        # Write the raw bytes to preserve color codes
                        sys.stdout.buffer.write(stdout)
                        sys.stdout.flush()
                        # For checking the content, decode without interpreting color codes
                        output += stdout.decode('utf-8', errors='replace')

                    if stderr:
                        sys.stderr.buffer.write(stderr)
                        sys.stderr.flush()
                        output += stderr.decode('utf-8', errors='replace')

                    # we can check output contains for any of the commands. Only error if it is the last command and we still have not found it
                    if self.commands[-1] == command and self.output_contains not in output:
                        response = f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
                        break
                    else:
                        if config.debugging:
                            print(f"Output contains: {self.output_contains}")
                else:
                    # For regular processes, wait and check return code
                    process.wait()
                    if process.returncode != 0:
                        response = f"Error running command: {command}"
                        break

        if self.post_delay > 0:
            print(f"Sleeping for {self.post_delay} seconds after running ...")
            for i in range(self.post_delay, 0, -1):
                print(f"Sleep: {i} seconds remaining...")
                time.sleep(1)

        if self.expect_failure:
            # if response is not None, then the cmd failed so the error was expected
            if response:
                return None
            else:
                return "Error: expected failure but command succeeded"

        return response



    def handle_delay(self, delay_type: Literal["post", "cmd"]) -> None:
        delay = self.post_delay if delay_type == "post" else self.cmd_delay

        if delay > 0:
            print(f"Sleeping for {delay} seconds after running  ({delay_type}_delay)...")
            for i in range(delay, 0, -1):
                print(f"Sleep: {i} seconds remaining...")
                time.sleep(1)

    def __str__(self):
        return f"DocsValue(language={self.language}, tags={self.tags}, ignored={self.ignored}, commands={self.commands}, background={self.background}, post_delay={self.post_delay}), cmd_delay={self.cmd_delay})"

    def print(self):
        print(self.__str__())

def cleanup_background_processes():
    """Kill all saved background processes"""
    if not background_processes:
        return

    print(f"\nCleaning up {len(background_processes)} background processes...")
    for pid in background_processes:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Terminated process with PID: {pid}")
        except OSError as e:
            # print(f"Error terminating process {pid}: {e}")
            pass

    # Clear the list
    background_processes.clear()


def extract_tag_value(tags, tag_type, default=None, converter=None):
    """
    Extract value from a tag of format 'tag_type=value' or 'tag_type="value with spaces"'
    """
    matching_tags = []

    for tag in tags:
        if tag_type in tag:
            # Find the position of the equals sign
            equals_pos = tag.find('=')
            if equals_pos != -1:
                # Get everything after the equals sign
                value = tag[equals_pos + 1:]

                # Check if the value starts with a quote
                if value and (value[0] == '"' or value[0] == "'"):
                    quote_char = value[0]
                    # Look for the matching closing quote
                    for i in range(1, len(value)):
                        if value[i] == quote_char:
                            # Extract the value WITHOUT quotes
                            value = value[1:i]
                            break
                else:
                    # No quotes, just use the value as is
                    value = value

                matching_tags.append(value)

    if not matching_tags:
        return default

    value = matching_tags[0]
    return converter(value) if converter else value

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

        value = DocsValue(
            language=language,
            tags=tags,
            content=content,
            ignored=ignored,
            background=(Tags.BACKGROUND() in tags),
            post_delay=extract_tag_value(tags, Tags.POST_DELAY(), default=0, converter=int),
            cmd_delay=extract_tag_value(tags, Tags.CMD_DELAY(), default=0, converter=int),
            binary=extract_tag_value(tags, Tags.IGNORE_IF_INSTALLED(), default=None),
            wait_for_endpoint=handle_http_polling_input(extract_tag_value(tags, Tags.HTTP_POLLING(), default=None)),
            commands=[],
            output_contains=extract_tag_value(tags, Tags.OUTPUT_CONTAINS(), default=None),
            expect_failure=(Tags.ASSERT_FAILURE() in tags),
            machine_os=(extract_tag_value(tags, Tags.MACHINE_OS(), default=None, converter=alias_operating_systems) or None),
            # file specific
            file_name=extract_tag_value(tags, Tags.FILE_NAME(), default=None),
            insert_at_line=extract_tag_value(tags, Tags.INSERT_AT_LINE(), default=None, converter=int),
            replace_lines=extract_tag_value(tags, Tags.REPLACE_AT_LINE(), default=None, converter=replace_at_line_converter),
            file_reset=(Tags.RESET_FILE() in tags),
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

        # Now set the attributes on your value object
        value.commands = commands
        results.append(value)

    return results

# input could be just a number ex: 3
# or a range of numbers; 2-4
def replace_at_line_converter(value: str) -> Tuple[int, int | None]:
    if '-' in value:
        start, end = value.split('-')
        return int(start), int(end)
    return int(value), None

def parse_env(command: str) -> Dict[str, str]:
    """
    Parse environment variable commands, handling backtick execution and inline env vars.

    Args:
        command: String containing potential env var assignments and commands

    Returns:
        Dictionary of environment variables (can be empty if no env vars found)
    """
    # Early return if no '=' is present in the command
    if '=' not in command:
        return {}

    # First check for export KEY=VALUE pattern
    export_match = re.match(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$', command.strip())
    if export_match:
        key = export_match.group(1)
        value = execute_substitution_commands(export_match.group(2))
        return {key: value}

    # Check for inline environment variables (KEY=VALUE command args)
    inline_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*=[^ ]+(?: [A-Za-z_][A-Za-z0-9_]*=[^ ]+)*) (.+)$', command.strip())
    if inline_match:
        env_vars = {}
        env_part = inline_match.group(1)

        # Extract all KEY=VALUE pairs
        for pair in env_part.split():
            if '=' in pair:
                key, value = pair.split('=', 1)
                env_vars[key] = execute_substitution_commands(value)

        return env_vars

    # Check for standalone KEY=VALUE
    standalone_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', command.strip())
    if standalone_match:
        key = standalone_match.group(1)
        value = execute_substitution_commands(standalone_match.group(2))
        return {key: value}

    # If we get here, there were no environment variables we could parse
    return {}


if __name__ == "__main__":
    main()
