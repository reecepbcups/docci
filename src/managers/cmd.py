import os
import platform
import shutil
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional, Union

import pexpect

from src.config import Config
from src.execute import (
    execute_command,
    execute_command_process,
    monitor_process,
    parse_env,
)
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
        background_exclude_commands: List[str] = [], # TODO: is this needed?
    ) -> str | None:
        if should_skip := self._should_skip_codeblock_execution(config):
            # print(f"{should_skip=}")
            return None

        response = None
        had_error = False

        for command in self.commands:
            if self._should_skip_cmd_execution(config, command):
                continue

            # Update global environment
            os.environ.update(parse_env(command))

            cmd_background = self._should_run_in_background(command, background_exclude_commands)
            # if cmd_background and not command.strip().endswith('&'): # TODO: seeing if it will just run in the background no issues
            #     command = f"{command} &" # TODO:

            if config.debugging:
                print(f"Running: {command=}, {cmd_background=}")

            # Handle pre-execution delay if set
            if self.delay_manager:
                self.delay_manager.handle_delay("cmd")

            # Execute command and handle result
            result = self._execute_command(command, os.environ.copy(), config, cmd_background)
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


    def run_background_process(self, command: str, config: Config) -> Optional[pexpect.spawn]:
        """
        Runs a command in the background using pexpect.

        Args:
            command (str): The command to execute.
        Returns:
            pexpect.spawn: The spawned process
        """
        try:
            process = execute_command_process(command, is_debugging=config.debugging, cwd=config.working_dir)
            pid = process.pid
            print(f"Background process started with PID: {pid}, cmd: {command}")


            # pass in monitor_process with is_background=True
            # Start a monitoring thread
            monitor_thread = threading.Thread(
                target=lambda x: monitor_process(x, is_background=True),
                args=(process,),
                daemon=True
            )
            monitor_thread.start()

            process_manager.add_process(pid, command)

            return process
        except Exception as e:
            print(f"Error starting background process: {e}")
            return None

    # TODO: remove cmd_background and just set if the line ends with &
    def _execute_command(self, command: str, env: dict, config: Config, cmd_background: bool) -> Union[str, bool, None]:
        """
        Execute a command and handle its output.
        Returns:
            - str: Error message if command failed
            - True: If stderr had output (error occurred)
            - None: If command executed successfully
        """
        if cmd_background:
            process = self.run_background_process(command, config)
            if process:
                print(f"--- Running command in background: {process.pid=}, {config.working_dir=}, {command=}")
            return None
        else:
            process = execute_command_process(command, cwd=config.working_dir)

        if self.output_contains:
            # TODO: while? or
            if process.isalive():
                try:
                    # Read any available output without blocking
                    o = process.read_nonblocking(size=1024, timeout=0.1)
                    if o:
                        output = o.decode('utf-8').strip()
                        print(f" --- output: {output}")

                        non_empty_commands = [cmd for cmd in self.commands if cmd.strip() and not cmd.strip().startswith('#')]
                        if non_empty_commands and command == non_empty_commands[-1]:
                            if self.output_contains not in output:
                                return f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
                            elif config.debugging:
                                print(f"Output contains: {self.output_contains}")

                except pexpect.TIMEOUT:
                    # No output available right now
                    pass
                except pexpect.EOF:
                    print("Process has ended")
        else:
            returncode = process.wait()
            print(f' -- return code {returncode}')
            if returncode != 0:
                return f"Error running command: {command}; returncode: {returncode}"


        # Handle foreground process
        # if self.output_contains:
        #     stdout, stderr = process.communicate()
        #     output = ""

        #     # Process stdout if any
        #     if stdout:
        #         sys.stdout.buffer.write(stdout)
        #         sys.stdout.flush()
        #         output += stdout.decode('utf-8', errors='replace')

        #     # Process stderr if any
        #     if stderr:
        #         sys.stderr.buffer.write(stderr)
        #         sys.stderr.flush()
        #         err = stderr.decode('utf-8', errors='replace')
        #         output += err
        #         if err:
        #             return True  # Indicates an error occurred

        #     # Only check output contains if this is the last non-empty command
        #     non_empty_commands = [cmd for cmd in self.commands if cmd.strip() and not cmd.strip().startswith('#')]
        #     if non_empty_commands and command == non_empty_commands[-1]:
        #         if self.output_contains not in output:
        #             return f"Error: `{self.output_contains}` is not found in output, output: {output} for {command}"
        #         elif config.debugging:
        #             print(f"Output contains: {self.output_contains}")
        # else:
        #     # Simple wait and check exit code
        #     process.wait()
        #     if process.returncode != 0:
        #         return f"Error running command: {command}"

        return None

    def _should_skip_cmd_execution(self, config:Config, command: str) -> bool:
        # Skip empty commands and comments
        if not command.strip() or command.strip().startswith('#'):
            return True

        if command in config.ignore_commands:
            return True
        return False

    def _should_skip_codeblock_execution(self, config: Config) -> bool:
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
