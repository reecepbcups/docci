import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

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
