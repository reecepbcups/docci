import os
import queue
import signal
import sys
import threading
import time

import pexpect


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

def execute_command(command: str, is_debugging: bool = False, is_background: bool = False,**kwargs) -> tuple[int, str] | pexpect.spawn:
    """Execute a shell command and return its exit status and output."""
    kwargs['env'] = kwargs.get('env', os.environ.copy())
    kwargs['withexitstatus'] = True

    assert 'cwd' in kwargs, "execute_command cwd must be provided"

    # ensure cwd exists, if not error
    if not os.path.exists(kwargs['cwd']):
        raise ValueError(f"cwd {kwargs['cwd']} does not exist")

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

repo_root = os.popen("git rev-parse --show-toplevel").read().strip()
node_ex_dir = os.path.join(repo_root, "examples", "1-node") ## ensures another cwd exists and works

# spawn = execute_command("ping 8.8.8.8", is_debugging=True, cwd=repo_root, is_background=True)
# print(spawn.pid)




# streaming_process = StreamingProcess("ping -n -i 0.1 8.8.8.8").start().attach_consumer(StreamingProcess.output_consumer)
streaming_process = StreamingProcess("ondod start").start().attach_consumer(StreamingProcess.output_consumer)

# iterate throguh numbers here
for i in range(10):
    print(i)
    time.sleep(1)

# kill the process
streaming_process.stop()
