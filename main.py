#!/usr/bin/env -S python3 -B

import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Literal

from config_types import Config
from execute import execute_substitution_commands
from models import Tags

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
                for i, value in enumerate(values):
                    if value.ignored:
                        continue

                    # the last command in the index and also the last file in all the paths
                    is_last_cmd = (i == len(values) - 1) and (file_path == file_paths[-1])
                    err = value.run_commands(config=config, is_last_cmd=is_last_cmd)
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
        cmd = sys.argv[0]
        if cmd.startswith('/tmp/staticx'):
            cmd = "docs-ci"

        print(f"Usage: {cmd} <config_path>")
        sys.exit(1)

    config_path = sys.argv[1]

    config: Config = Config.load_from_file(config_path)

    err = do_logic(config)
    if err:
        print(err)
        sys.exit(1)

@dataclass
class DocsValue:
    language: str # bash, python, rust, etc
    tags: List[str] # (e.g., 'docs-ci-ignore') in the ```bash tag1, tag2```
    content: str # unmodified content
    ignored: bool
    commands: List[str]
    background: bool = False # if the command should run in the background i.e. it is blocking
    post_delay: int = 0 # delay in seconds after the command is run
    cmd_delay: int = 0 # delay in seconds before each command is run
    # docs-ci-wait-for-endpoint=http://127.0.0.1:8000|30 tag would be nice (after 30 seconds, fail)

    def run_commands(
        self,
        config: Config,
        background_exclude_commands: List[str] = ["cp", "export", "cd", "mkdir", "echo", "cat"],
        is_last_cmd: bool = False,
        cwd: str | None = None,
    ) -> str | None:
        '''
        Runs the commands. host env vars are pulled into the processes

        returns: error message if any
        '''

        env = os.environ.copy()

        success = None

        for command in self.commands:
            if command in config.ignore_commands:
                continue

            # parse out env vars from commands. an example format is:
            # --> export SERVICE_MANAGER_ADDR=`make get-eigen-service-manager-from-deploy
            # this should be done here as it is more JIT, can't do earlier else other commands are not ready
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

            if config.debug:
                print(f"Running command: {command}" + (" (& added for background)" if cmd_background else ""))

            if self.cmd_delay > 0:
                print(f"Sleeping for {self.cmd_delay} seconds before running command (cmd-delay)...")
                for i in range(self.cmd_delay, 0, -1):
                    print(f"Sleep: {i} seconds remaining...")
                    time.sleep(1)

            process = process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE if is_last_cmd else None,
                stderr=subprocess.PIPE if is_last_cmd else None,
                shell=True,
                env=env,
                cwd=cwd,
                text=False,
            )

            if cmd_background:
                if process.pid:
                    background_processes.append(process.pid)
            else:
                if is_last_cmd:
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

                    if config.final_output_contains not in output:
                        success = f"Error: final_output_contains not found in output: {config.final_output_contains}"
                        break
                else:
                    # For regular processes, wait and check return code
                    process.wait()
                    if process.returncode != 0:
                        success = f"Error running command: {command}"
                        break

        if self.post_delay > 0:
            print(f"Sleeping for {self.post_delay} seconds after running commands...")
            for i in range(self.post_delay, 0, -1):
                print(f"Sleep: {i} seconds remaining...")
                time.sleep(1)

        return success

    def handle_delay(self, delay_type: Literal["post", "cmd"]) -> None:
        delay = self.post_delay if delay_type == "post" else self.cmd_delay

        if delay > 0:
            print(f"Sleeping for {delay} seconds after running commands ({delay_type}_delay)...")
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

    print(f"Cleaning up {len(background_processes)} background processes...")
    for pid in background_processes:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Terminated process with PID: {pid}")
        except OSError as e:
            # print(f"Error terminating process {pid}: {e}")
            pass

    # Clear the list
    background_processes.clear()




def parse_markdown_code_blocks(config: Config | None, content: str) -> List[DocsValue]:
    """
    Parse a markdown file and extract all code blocks with their language and content.

    Args:
        content: A files contents as a string

    Returns:
        A list of dictionaries, each containing:
        - 'language': The language of the code block
        - 'content': The content of the code block
        - 'should_run': Boolean indicating if this block should be executed (True for bash blocks without docs-ci-ignore)
    """

    # Regex pattern to match code blocks: ```language ... ```
    # Capturing groups:
    # 1. Language and any additional markers (e.g., 'bash docs-ci-ignore')
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
        tags = language_parts[1:] if len(language_parts) > 1 else []

        ignored = Tags.IGNORE() in tags
        if config is not None:
            ignored = ignored or language not in config.followed_languages

        background = Tags.BACKGROUND() in tags
        post_delay = int([tag.split('=')[1] for tag in tags if Tags.POST_DELAY() in tag][0]) if any('docs-ci-post-delay' in tag for tag in tags) else 0
        cmd_delay = int([tag.split('=')[1] for tag in tags if Tags.CMD_DELAY() in tag][0]) if any('docs-ci-cmd-delay' in tag for tag in tags) else 0

        content = str(block_content).strip()

        value = DocsValue(
            language=language,
            tags=tags,
            content=content,
            ignored=ignored,
            background=background,
            post_delay=post_delay,
            cmd_delay=cmd_delay,
            commands=[]
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
