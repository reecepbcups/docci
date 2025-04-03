import os
import queue
import re
import threading
import time

import pexpect


# execute_substitution_commands  is from execute.py
def execute_substitution_commands(value: str, **kwargs) -> str:
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
        (r'`(.*?)`', lambda match: execute_command(match.group(1), **kwargs)),
        (r'\$\((.*?)\)', lambda match: execute_command(match.group(1), **kwargs))
    ]

    for pattern, handler in patterns:
        # Keep replacing until no more matches
        while True:
            match = re.search(pattern, result)
            if not match:
                break

            full_match = match.group(0)
            replacement = handler(match)
            result = result.replace(full_match, replacement[1]) # TODO: I just change this to grab from the tuple from the output (since status is returned in index 0)

    return result


# StreamingProcess for background running instances we want to still stream output for
class StreamingProcess:
    def __init__(self, command, encoding='utf-8'):
        self.command = command
        self.encoding = encoding
        self.process = None
        self.output_queue = queue.Queue()
        self.read_thread = None  # Separate thread for reading output
        self.consume_thread = None # Separate thread for consuming output
        self.is_running = False

    def start(self) -> "StreamingProcess":
        self.is_running = True
        self.process = pexpect.spawn(self.command, encoding=self.encoding)
        self.read_thread = threading.Thread(target=self._read_output, daemon=True)
        self.read_thread.start()
        return self

    def _read_output(self):
        try:
            while self.is_running:
                try:
                    line = self.process.readline()
                except pexpect.exceptions.EOF:
                    break # Expected when process finishes
                except OSError as e:
                    # Handle "Bad file descriptor" error gracefully, especially after process termination
                    if e.errno == 9:  #errno.EBADF
                        break
                    else:
                        print(f"Unexpected OSError in read_output: {e}")
                        break
                except Exception as e:
                    print(f"Error reading output: {e}")
                    break

                if not line:
                    break  # Process finished or EOF
                self.output_queue.put(line)
        finally:
            self.stop()  # Ensure cleanup

    def attach_consumer(self, consumer_function) -> "StreamingProcess":
         """Attaches a consumer function to process the output in a non blocking way."""
         self.consume_thread = threading.Thread(target=self._consume_output, args=(consumer_function,), daemon=True)
         self.consume_thread.start()
         return self

    @staticmethod
    def output_consumer(line: str):
        """Example consumer function: prints the line to stdout."""
        print(line.strip())

    def _consume_output(self, consumer_function):
        try:
            while self.is_running or not self.output_queue.empty():
                try:
                    line = self.output_queue.get(timeout=1)  # Adjusted timeout
                    if line:
                        consumer_function(line)
                    else:
                        time.sleep(0.1)  # Prevent busy-waiting
                except queue.Empty:
                    # Queue is empty, but the process might still be running, so keep trying
                    pass

        except Exception as e:
            print(f"Error consuming output: {e}")
        finally:
            pass

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.process:
                try:
                    self.process.close(force=True)  # Terminate the process
                except:
                    pass  # Handle potential errors when closing
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=2)  # Wait for thread to finish
            if self.consume_thread and self.consume_thread.is_alive():
                self.consume_thread.join(timeout=2)

            print(f"StreamingProcess stopped for {self.command=}")

def execute_command(command: str, is_debugging: bool = False, is_background: bool = False, **kwargs) -> tuple[int, str] | pexpect.spawn:
    """Execute a shell command and return its exit status and output."""
    kwargs['env'] = kwargs.get('env', os.environ.copy())
    kwargs['withexitstatus'] = True

    assert 'cwd' in kwargs, "execute_command cwd must be provided"

    # ensure cwd exists, if not error
    if not os.path.exists(kwargs['cwd']):
        raise ValueError(f"cwd {kwargs['cwd']} does not exist")

    # TODO: process if it is an env var and pass through `` and $()

    # if is_debugging:
    print(f"    Executing {command=} in {kwargs['cwd']=}")

    if not is_background:
        result, status = pexpect.run(f'''bash -c "{command}"''', **kwargs)
        return status, result.decode('utf-8').replace("\r\n", "")

    kwargs.pop('withexitstatus')
    # f = open(os.path.join(kwargs['cwd'], "logfile.txt"), "wb")
    spawn = pexpect.spawn(f"{command}", **kwargs)
    # TODO: cleanup PID later
    return spawn

status, res = execute_command("echo 12345", is_debugging=True, cwd=os.getcwd())
print(status, res)

# repo_root = os.popen("git rev-parse --show-toplevel").read().strip()
# node_ex_dir = os.path.join(repo_root, "examples", "1-node") ## ensures another cwd exists and works

# spawn = execute_command("ping 8.8.8.8", is_debugging=True, cwd=repo_root, is_background=True)
# print(spawn.pid)

# set env variable DEPLOYER_PRIV_KEY to `DEPLOYER_PRIV_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80`
os.environ['DEPLOYER_PRIV_KEY'] = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'

# working input example
print(execute_command('echo "12345678" | ondod keys unsafe-import-eth-key test-deploy-acc ${DEPLOYER_PRIV_KEY} --keyring-backend test', is_debugging=True, cwd=os.getcwd()))
print(execute_command('ondod keys delete test-deploy-acc <<< "Y"', is_debugging=True, cwd=os.getcwd()))

# streaming_process = StreamingProcess("ondod start").start().attach_consumer(StreamingProcess.output_consumer)

# PRIV_KEY=2C5F0E00617B6849F8EFD5D74DB1D06D7E516A8B6FF86F6059B024B22D5EACCF
ENV_SET=execute_substitution_commands('PRIV_KEY=`ondod keys unsafe-export-eth-key acc0`', cwd=os.getcwd())

# now take this, parse, and set the os env vars
k, v = ENV_SET.split("=")
os.environ.update({k: v})

print(execute_command('echo hello ${PRIV_KEY}', cwd=os.getcwd())[1])

time.sleep(1)

# streaming_process = StreamingProcess("ping -n -i 0.1 8.8.8.8").start().attach_consumer(StreamingProcess.output_consumer)


# for i in range(6):
#     print(i); time.sleep(1)

# streaming_process.stop()
