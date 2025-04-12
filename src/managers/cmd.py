import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from logging import getLogger
from typing import List, Optional, Union

from pexpect import spawn

from src.config import Config
from src.execute import execute_command, parse_env
from src.managers.delay import DelayManager


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
    retry_count: int = 0
    replace_text: Optional[str] = None

    def run_commands(
        self,
        config: Config,
        background_exclude_commands: List[str] = ["cp", "export", "cd", "mkdir", "echo", "cat"], # TODO: remove?
    ) -> str | None:
        if self._should_skip_codeblock_execution(config):
            return None

        response = None
        had_error = False

        for command in self.commands:
            if self._should_skip_cmd_execution(config, command):
                continue

            # Update global environment (and persist through the future codeblock sections on this test)
            # _execute_command will load in this
            envs = parse_env(command)
            os.environ.update(envs)

            cmd_background = self._should_run_in_background(command, background_exclude_commands)

            getLogger(__name__).debug(f"\t{envs=},{cmd_background=}")

            # Handle pre-execution delay if set
            if self.delay_manager:
                self.delay_manager.handle_delay("cmd")

            # Execute command and handle result
            # this passes the os.environ copy due to working with multiple threads
            result = self._execute_command(command, config, cmd_background, env=os.environ.copy())
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

    def _handle_retry_cmd_delay(self, attempt: int = -1):
        assert attempt >= 0, "Attempt must be a non-negative integer"
        if attempt == 1: return

        delay_second = 2
        if self.delay_manager:
            if self.delay_manager.cmd_delay > 0:
                delay_second = self.delay_manager.cmd_delay
        getLogger(__name__).debug(f"Sleeping for {delay_second} seconds before retrying...")
        time.sleep(delay_second)

    def _execute_command(self, command: str, config: Config, cmd_background: bool, env: dict) -> Union[str, bool, None]:
        """
        Execute a command and handle its output.
        Returns:
            - str: Error message if command failed
            - True: If stderr had output (error occurred)
            - None: If command executed successfully
        """
        # Handle text replacement if configured
        if self.replace_text:
            try:
                parts = self.replace_text.split(';')
                if len(parts) != 2:
                    return f"Error: invalid format for docci-replace-text. Expected format: 'text;ENV_VAR', got '{self.replace_text}'"

                text_to_replace, env_var_name = parts

                # Check if the environment variable exists
                if env_var_name not in env:
                    return f"Error: environment variable '{env_var_name}' not set. Required by docci-replace-text."

                env_var_value = env[env_var_name]
                getLogger(__name__).debug(f"Replacing '{text_to_replace}' with env var {env_var_name}='{env_var_value}' in command: {command}")

                # Replace the text in the command
                command = command.replace(text_to_replace, env_var_value)
                getLogger(__name__).debug(f"Command after replacement: {command}")
            except Exception as e:
                return f"Error in text replacement: {str(e)}"

        # Retry logic
        max_attempts = max(1, self.retry_count + 1)  # At least 1 attempt
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            getLogger(__name__).debug(f"Executing command (attempt {attempt}/{max_attempts}): {command}")

            working_dir = config.working_dir if config else os.getcwd()
            tmp = execute_command(command, is_background=cmd_background, cwd=working_dir, env=env)

            # already handled in execute_command to run a background process thread
            if cmd_background:
                # process: spawn = tmp
                return None

            status: int | None = tmp[0]
            output: str = tmp[1]

            # For output_contains check
            if self.output_contains:
                # Only check output contains if this is the last non-empty command
                non_empty_commands = [cmd for cmd in self.commands if cmd.strip() and not cmd.strip().startswith('#')]
                if non_empty_commands and command == non_empty_commands[-1]:
                    if self.output_contains not in output:
                        # If we've reached max attempts, return error
                        if attempt >= max_attempts:
                            return f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
                        getLogger(__name__).debug(f"Retry {attempt}/{max_attempts}: Output missing required text, retrying...")

                        self._handle_retry_cmd_delay(attempt)
                        continue  # Try again

                    getLogger(__name__).debug(f"\tOutput contains: '{self.output_contains}' for {command=}\n")
                    return None  # Success

            # For status check
            else:
                if status is None:
                    return None

                if status != 0:
                    # If we've reached max attempts, return error
                    if attempt >= max_attempts:
                        return f"Error ({status=}) {command=} failed with output: {output}"
                    getLogger(__name__).debug(f"Retry {attempt}/{max_attempts}: Command failed with status {status}, retrying...")
                    self._handle_retry_cmd_delay(attempt)
                    continue  # Try again

            # If we get here, the command succeeded
            return None

        # Should not reach here due to returns in the loop
        return None

    def _should_skip_codeblock_execution(self, config: Config) -> bool:
        """Check various conditions that would cause us to skip command execution."""
        # Skip if marked as ignored
        if self.ignored:
            getLogger(__name__).debug(f"Ignoring commands... ({self.commands})")
            return True

        # Skip if target file already exists
        if self.if_file_not_exists:
            working_dir = config.working_dir if config else os.getcwd()
            file_path = os.path.join(working_dir, self.if_file_not_exists) if config.working_dir else self.if_file_not_exists
            if os.path.exists(file_path):
                getLogger(__name__).debug(f"Skipping commands since {file_path} exists")
                return True

        # Skip if OS doesn't match
        system = platform.system().lower()
        if self.machine_os and self.machine_os != system:
            getLogger(__name__).debug(f"Skipping command since it is not for the current OS: {self.machine_os}, current: {system}")
            return True

        # Skip if binary is already installed
        if self.binary and shutil.which(self.binary):
            getLogger(__name__).debug(f"Skipping command since {self.binary} is already installed.")
            return True

        return False

    def _should_skip_cmd_execution(self, config: Config, command: str) -> bool:
        # Skip empty commands and comments
        if not command.strip() or command.strip().startswith('#'):
            return True

        if config and command in config.ignore_commands:
            return True
        return False

    def _should_run_in_background(self, command: str, exclude_commands: List[str]) -> bool:
        if not self.background:
            return False
        first_word = command.strip().split()[0]
        return first_word not in exclude_commands
