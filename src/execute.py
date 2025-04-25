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

    # Special handling for export commands - execute them separately and update env
    if command.strip().startswith('export '):
        envs = parse_env(command)
        if envs:
            # Update our environment with the exported variables
            os.environ.update(envs)
            # Log for debugging
            getLogger(__name__).debug(f"\tEnvironment updated with exported variables: {envs}")
            # For export commands, return success with empty output
            return 0, ""

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
    getLogger(__name__).debug(f"Executing substitution in: {value}")

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
            cmd_to_run = match.group(1)
            getLogger(__name__).debug(f"Found command substitution: {cmd_to_run}")
            
            # Execute the command and get its output
            status, output = execute_command(cmd_to_run, env=os.environ.copy())
            if status != 0:
                getLogger(__name__).warning(f"Command substitution failed: {cmd_to_run}, status: {status}")
                
            # Replace the entire command (including backticks/$()), with the command's output
            result = result.replace(full_match, output.strip())
            getLogger(__name__).debug(f"Substituted {full_match} with: '{output.strip()}'")

    getLogger(__name__).debug(f"After substitution: {result}")
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
        value = export_match.group(2).strip()
        
        # Handle backtick command execution for export
        if '`' in value or '$(' in value:
            # Remove outer quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
                
            # Execute the substitution command and use its output as the value
            value = execute_substitution_commands(value)
            getLogger(__name__).debug(f"Executed substitution for {key}={value}")
        
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
                if '`' in value or '$(' in value:
                    value = execute_substitution_commands(value)
                env_vars[key] = value

        return env_vars

    # Check for standalone KEY=VALUE
    standalone_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', command.strip())
    if standalone_match:
        key = standalone_match.group(1)
        value = standalone_match.group(2).strip()
        
        # Handle backtick command execution for standalone assignment
        if '`' in value or '$(' in value:
            value = execute_substitution_commands(value)
            
        return {key: value}

    # If we get here, there were no environment variables we could parse
    return {}

# validate_command handles 1 edge case where a nested double quote is used in a command
# that breaks. I think this is something specific to the forge (ethereum tool) command line.
def validate_command(cmd: str) -> Optional[str]:
    if 'forge script' in cmd and '\\\"' in cmd:
        return "Please use single quotes for forge script `--sig`, not double quotes"

    return None