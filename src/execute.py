import os
import re
from typing import Dict

# import subprocess
import pexpect


# TODO: resultOnly is only used in execute_substitution_commands, simplify back to not including.
def execute_command(command: str, resultOnly: bool = False) -> tuple[int, str]:
    """Execute a shell command and return its exit status and output."""
    result, status = pexpect.run(f'''bash -c "{command}"''', env=os.environ, cwd=None,  withexitstatus=True)
    res = result.decode('utf-8').replace("\r\n", "")
    if resultOnly:
        return res
    return status, res


# TODO: simplify?
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
        (r'`(.*?)`', lambda match: execute_command(match.group(1), resultOnly=True)),
        (r'\$\((.*?)\)', lambda match: execute_command(match.group(1), resultOnly=True))
    ]

    for pattern, handler in patterns:
        # Keep replacing until no more matches
        while True:
            match = re.search(pattern, result)
            if not match:
                break

            full_match = match.group(0)
            replacement = handler(match)
            result = result.replace(full_match, replacement)

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
