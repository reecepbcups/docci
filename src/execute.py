import os
import re
import sys
from logging import getLogger
from typing import Dict, Optional

import pexpect

from src.managers.process import process_manager
from src.managers.streaming import StreamingProcess


def execute_command(command: str, is_background: bool = False, **kwargs) -> tuple[int, str] | pexpect.spawn:
    """Execute a shell command and return its exit status and output."""
    kwargs['env'] = kwargs.get('env', os.environ.copy())

    kwargs['cwd'] = kwargs.get('cwd', os.getcwd())
    if kwargs['cwd'] is None:
        kwargs['cwd'] = os.getcwd()
    if not os.path.exists(kwargs['cwd']):
        raise ValueError(f"cwd {kwargs['cwd']} does not exist")

    # If using docci-background and command ends with " &", remove the trailing " &"
    if is_background and command.strip().endswith(" &"):
        command = command.strip()[:-2]
        getLogger(__name__).debug(f"\tRemoved trailing ' &' from background command")

    # Handle source commands
    isSource = False
    SPECIAL_DELIM = "__DOCCI_ENV_VAR_DELIM__"
    if command.strip().lower().startswith("source "):
        isSource = True
        # 1. Get the current env from the system
        # 2. Run the command & print out the output from the command
        # 3. `diff / comm` the output and set those new values as an env for all future execution

        # append '&& env' to the command to print out the env variables after sourcing
        # use a specific delim to make it easier to parse the output for env
        command += f" && echo {SPECIAL_DELIM} && env"
        getLogger(__name__).debug(f"\tSourcing command: {command}")


    # TODO: process if it is an env var and pass through `` and $()

    getLogger(__name__).debug(f"\tExecuting: {command=} in {kwargs['cwd']}")

    if error := validate_command(command):
        getLogger(__name__).error(f"\tError: {error}")
        return 1, error

    # command may ONLY be a single line that is a bash env variable export. How can I check for this in pexpect?
    cmd = f'''bash -c "{command}"'''
    timeout = None

    if not is_background:
        kwargs['withexitstatus'] = True
        env = os.environ.copy()  # Start with a copy of the current env
        env.update(
            kwargs.pop("env", {})
        )  # Update with any env vars passed in kwargs
        result, status = pexpect.run(cmd, env=env, timeout=timeout, **kwargs)

        new_vars = {}
        if isSource:

            # parse the output to get the special delimter values after since this is a source command. Then update the env
            output = result.decode('utf-8').strip()
            if SPECIAL_DELIM in output:
                # print(output)

                # Split the output into lines
                lines = output.splitlines()
                # Find the index of the special delimiter
                delim_index = lines.index(SPECIAL_DELIM)
                # The new env vars are everything after the delimiter
                new_env_vars = lines[delim_index + 1:]

                # Update the environment with the new variables
                for var in new_env_vars:
                    if '=' in var:
                        key, value = var.split('=', 1)
                        new_vars[key] = value.strip()
                        # os.environ[key] = value.strip()
                        getLogger(__name__).debug(f"\tUpdated env var: {key=} {value.strip()}")

        # update the global env with the diff values from new_vars
        diff = dict_diff(os.environ, new_vars)
        if diff:
            getLogger(__name__).debug(f"\tUpdating global env with: {diff=}")
            os.environ.update(dict(diff))

        # if isSource, we should not print out anythiung
        if isSource:
            # return 0, "Sourced successfully"
            return 0, ""

        # (cosmetic) sometimes color is not set so a previous end of command color is used.
        # if the result has a proper color code then that will be used instead.
        reset_color = b"\x1b[0m"
        if status == 0:
            sys.stdout.buffer.write(reset_color + result); sys.stdout.flush()
        else:
            sys.stderr.buffer.write(reset_color + result); sys.stderr.flush()

        # Replace only \r\n with \n to standardize line endings, but preserve the newlines
        decoded = result.decode('utf-8').replace("\r\n", "\n").strip()
        return status, decoded


    spawn = StreamingProcess(cmd, cwd=kwargs['cwd'], timeout=timeout).start().attach_consumer(StreamingProcess.output_consumer)
    process = spawn.process
    if process.pid:
        process_manager.add_process(spawn, command)
    return process

def execute_substitution_commands(value: str) -> str:
    """
    Execute commands inside backticks or $() and return the value with output substituted.

    Args:
        value: String that may contain backtick or $() commands

    Returns:
        String with commands replaced by their output
    """
    result = value

    # Process all commands
    patterns = [
        (r'`(.*?)`', lambda match: execute_command(match.group(1))),
        (r'\$\((.*?)\)', lambda match: execute_command(match.group(1)))
    ]

    for pattern, handler in patterns:
        # Keep replacing until no more matches
        while True:
            match = re.search(pattern, result)
            if not match:
                break

            full_match = match.group(0)
            replacement = handler(match)
            result = result.replace(full_match, replacement[1]) # returns tuple[int, str] from the execute_command

    return result

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

# validate_command handles 1 edge case where a nested double quote is used in a command
# that breaks. I think this is something specific to the forge (ethereum tool) command line.
def validate_command(cmd: str) -> Optional[str]:
    if 'forge script' in cmd and '\\\"' in cmd:
        return "Please use single quotes for forge script `--sig`, not double quotes"

    return None

def dict_diff(before, after) -> dict[str, str]:
    added = {k: v for k, v in after.items() if k not in before}
    changed = {k: after[k] for k in before if k in after and before[k] != after[k] and isinstance(after[k], str)}

    return {**added, **changed} if added or changed else {}
