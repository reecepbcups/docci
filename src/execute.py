import os
import re
import time
from typing import Dict

import pexpect


def execute_command(command: str, **kwargs) -> tuple[int, str]:
    """Execute a shell command and return its exit status and output."""
    kwargs['env'] = kwargs.get('env', os.environ.copy())
    kwargs['withexitstatus'] = True

    # TODO: logfile=None
    result, status = pexpect.run(f'''bash -c "{command}"''', **kwargs)
    return status, result.decode('utf-8').replace("\r\n", "")

# make sure this matches `execute_command` pretty closely
def execute_command_process(command: str, is_debugging: bool = False, **kwargs) -> pexpect.spawn:
    """Execute a shell command and return its process."""
    is_background = kwargs.pop('background', False)

    spawn_kwargs = {
        'env': kwargs.get('env', os.environ.copy()),
        'cwd':  kwargs.get('cwd', None),
    }

    if is_debugging:
        print(f" --- {spawn_kwargs['cwd']=}, {is_background=}, {command=}")

    # Don't wrap background commands in bash -c to prevent premature termination
    if is_background:
        return pexpect.spawn(f"{command}", **spawn_kwargs)
    else:
        return pexpect.spawn(f'''bash -c "{command}"''', **spawn_kwargs)

# use with `execute_command_process`
def monitor_process(proc: pexpect.spawn, is_background=False) -> None:
    """Function to run in a separate thread that monitors the process"""

    # if is_background then we do not expect anything, just sleep? or just verify it is alive still?
    if is_background:
        try:
            while True:
                time.sleep(1)
        except Exception as e:
            print(f"Exception in monitor thread: {e}")

    try:
        # time.sleep(0.5)  # Give the background process a chance to start
        # This will block in the thread but not the main program
        proc.expect(pexpect.EOF, timeout=None)
        print("Process has terminated naturally", proc.pid)
    except Exception as e:
        print(f"Exception in monitor thread: {e}")

def execute_substitution_commands(value: str) -> str:
    """
    Execute commands inside backticks or $() and return the value with output substituted.
    """
    result = value

    # Process all backtick commands
    while '`' in result:
        match = re.search(r'`(.*?)`', result)
        if not match:
            break
        cmd = match.group(1)
        _, output = execute_command(cmd)
        result = result.replace(match.group(0), output)

    # Process all $() commands
    while '$(' in result:
        match = re.search(r'\$\((.*?)\)', result)
        if not match:
            break
        cmd = match.group(1)
        _, output = execute_command(cmd)
        result = result.replace(match.group(0), output)

    return result

# TODO: is $(command) supported here as well?
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

    # TODO: how to merge this with the normal, we should not need an export specific method.
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
