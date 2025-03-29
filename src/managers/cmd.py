import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Union

from src.config import Config
from src.execute import parse_env
from src.managers.delay import DelayManager
from src.processes_manager import process_manager


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
        if skip_reason := self._should_skip_execution(config):
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

            # Handle pre-execution delay if set
            if self.delay_manager:
                self.delay_manager.handle_delay("cmd")

            # Execute command and handle result
            result = self._execute_command(command, env, config, cmd_background)
            if isinstance(result, str):
                response = result
                break
            elif result is True:  # Had error
                had_error = True

        if self.delay_manager:
            self.delay_manager.handle_delay("post")

        if self.expect_failure:
            if had_error:
                return None
            else:
                return "Error: expected failure but command succeeded"

        return response

    def _execute_command(self, command: str, env: dict, config: Config, cmd_background: bool) -> Union[str, bool, None]:
        """
        Execute a command and handle its output.
        Returns:
            - str: Error message if command failed
            - True: If stderr had output (error occurred)
            - None: If command executed successfully
        """
        # Extract stdin data from heredoc if present
        stdin_data = None

        if "<<<" in command:
            cmd_parts = command.split("<<<")
            command = cmd_parts[0].strip()
            stdin_data = cmd_parts[1].strip()

            # Handle variable substitution in stdin data
            if stdin_data.startswith("${") and stdin_data.endswith("}"):
                var_name = stdin_data[2:-1]
                stdin_data = env.get(var_name, "")
                # If the value contains spaces, wrap it in single quotes
                if ' ' in stdin_data and not (stdin_data.startswith("'") and stdin_data.endswith("'")):
                    stdin_data = f"'{stdin_data}'"

            # Handle quoted strings only if not already handled by env var
            elif stdin_data.startswith('"') and stdin_data.endswith('"'):
                stdin_data = stdin_data[1:-1]  # Remove outer quotes
            elif stdin_data.startswith("'") and stdin_data.endswith("'"):
                stdin_data = stdin_data[1:-1]  # Remove outer quotes

            # Add newline if not present
            if not stdin_data.endswith('\n'):
                stdin_data += '\n'

        elif "|" in command:
            # Handle piped commands
            cmd_parts = command.split("|")
            input_cmd = cmd_parts[0].strip()
            command = "|".join(cmd_parts[1:]).strip()

            # Special handling for echo commands with variables
            if input_cmd.startswith('echo "') and '"' in input_cmd:
                # Extract the variable name from echo "${VAR_NAME}"
                var_match = re.search(r'echo "\${([^}]+)}"', input_cmd)
                if var_match:
                    var_name = var_match.group(1)
                    stdin_data = env.get(var_name, "")
                    if stdin_data and not stdin_data.endswith('\n'):
                        stdin_data += '\n'
            else:
                # Execute the input command to get stdin data
                input_process = subprocess.Popen(
                    input_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    env=env,
                    cwd=config.working_dir,
                    text=True
                )
                stdin_data_raw, _ = input_process.communicate()
                if stdin_data_raw:
                    stdin_data = stdin_data_raw.strip()
                    if not stdin_data.endswith('\n'):
                        stdin_data += '\n'

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE if self.output_contains else None,
            stderr=subprocess.PIPE if self.output_contains else None,
            stdin=subprocess.PIPE,
            shell=True,
            env=env,
            cwd=config.working_dir,
            text=True,
        )

        if cmd_background:
            if process.pid:
                process_manager.add_process(process.pid)
            return None

        if self.output_contains:
            stdout, stderr = process.communicate(input=stdin_data)
            output = ""

            # Process stdout if any
            if stdout:
                sys.stdout.write(stdout)
                sys.stdout.flush()
                output += stdout

            # Process stderr if any
            if stderr:
                sys.stderr.write(stderr)
                sys.stderr.flush()
                output += stderr
                if stderr:
                    return True  # Indicates an error occurred

            # Check if expected output is present in final command
            if self.commands[-1] == command and self.output_contains not in output:
                return f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
            elif config.debugging:
                print(f"Output contains: {self.output_contains}")
        else:
            # Simple wait and check exit code
            process.communicate(input=stdin_data)
            if process.returncode != 0:
                return f"Error running command: {command}"

        return None

    def _should_skip_execution(self, config: Config) -> bool:
        """Check various conditions that would cause us to skip command execution."""
        # Skip if marked as ignored
        if self.ignored:
            if config.debugging:
                print(f"Ignoring commands... ({self.commands}))")
            return True

        # Skip if target file already exists
        if self.if_file_not_exists:
            file_path = os.path.join(config.working_dir, self.if_file_not_exists) if config.working_dir else self.if_file_not_exists
            if os.path.exists(file_path):
                if config.debugging:
                    print(f"Skipping commands since {file_path} exists")
                return True

        # Skip if OS doesn't match
        system = platform.system().lower()
        if self.machine_os and self.machine_os != system:
            if config.debugging:
                print(f"Skipping command since it is not for the current OS: {self.machine_os}, current: {system}")
            return True

        # Skip if binary is already installed
        if self.binary and shutil.which(self.binary):
            print(f"Skipping command since {self.binary} is already installed.")
            return True

        return False

    def _should_run_in_background(self, command: str, exclude_commands: List[str]) -> bool:
        if not self.background:
            return False
        first_word = command.strip().split()[0]
        return first_word not in exclude_commands
