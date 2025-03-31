import os
import threading
import time

import pexpect

# shell = pexpect.spawn('bash')
# shell.expect('[$#] ') # Wait for bash prompt

# # child.expect('Name .*: ') << this works to then send in lines?
# shell.sendline('x=500')
# shell.expect('[$#] ') # Wait for bash prompt

# shell.sendline('echo $x')
# shell.expect('[$#] ') # Wait for bash prompt

# # Get the output
# output = shell.before.decode('utf-8')
# print(f"Output from command: {output}")


# result = pexpect.run('bash -c "x=500; echo $x"').decode('utf-8')
# print(f"Output from command: {result}")

# random stdin
# result = pexpect.run('''bash -c "
# python3 demo/in.py <<< '500'
# echo "501" | python3 demo/in.py
# "''').decode('utf-8')
# print(result)

# precompile control panel
# result = pexpect.run('''bash -c "
# PRECOMPILE_ADDR=0x0000000000000000000000000000000000000901
# WALLET_ADDR=`ondod keys show acc0 -a`
# PRIV_KEY=`ondod keys unsafe-export-eth-key acc0`
# cast send --private-key ${PRIV_KEY} ${PRECOMPILE_ADDR} 'updateParams(string authority, string admin, bool enabled, string[] validators)' "${WALLET_ADDR}" "${WALLET_ADDR}" true "[${WALLET_ADDR}]"
# "''').decode('utf-8')
# print(result)

def parse_envs_from_lines(lines: str | list[str]) -> dict[str, str]:
    if isinstance(lines, list):
        lines = "\n".join(lines)

    envs = {}
    for line in lines.split("\n"):
        if not line.strip():
            continue

        if "=" not in line:
            continue

        # TODO: use regex because this fails
        key, value = line.split("=")

        # if value is wrapped in backticks, then we need to evaluate it
        if value.startswith("`") and value.endswith("`"):
            value = value[1:-1]
            value = run_commands(value, returnDecoded=True)
        # or $( and )
        elif value.startswith("$(") and value.endswith(")"):
            value = value[2:-1]
            value = run_commands(value, returnDecoded=True)

        if value.endswith("\r\n"):
            value = value[:-2]

        envs[key] = value

    return envs

def run_commands(lines: str | list[str], returnDecoded: bool = True) -> str:
    if isinstance(lines, str):
        lines = lines.split("\n")

    # now we can insert delays after each line if we need too based on tags


    os.environ.update(parse_envs_from_lines(lines))

    # withexitstatus=1
    # then -> (command_output, exitstatus) = run
    # events={'(?i)password':'secret\\n'} is input if ever seen


    lines = "\n".join(lines)
    result, status = pexpect.run(f'''bash -c "{lines}"''', env=os.environ, cwd=None,  withexitstatus=True)
    if status != 0:
        raise Exception(f"Failed to run commands: status: {status} {result}")
    return result.decode('utf-8') if returnDecoded else result

# result = pexpect.run('''bash -c "
# DEPLOYER_PRIV_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
# DEPLOYER=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
# # ERC20 contract address (not yet deployed)
# CONTRACT=0x5FbDB2315678afecb367f032d93F642f64180aa3
# echo "12345678" | ondod keys unsafe-import-eth-key test-deploy-acc ${DEPLOYER_PRIV_KEY} --keyring-backend=test

# echo "test"
# "''').decode('utf-8')
# print(result)

result = run_commands('''
DEPLOYER_PRIV_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
DEPLOYER=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
# ERC20 contract address (not yet deployed)
CONTRACT=0x5FbDB2315678afecb367f032d93F642f64180aa3
VALUE2=`echo 12345`
echo "12345678" | ondod keys unsafe-import-eth-key test-deploy-acc ${DEPLOYER_PRIV_KEY} --keyring-backend test
# echo "test"

#   delete that  key
ondod keys delete test-deploy-acc <<< "Y"
''')
print(result)

result = run_commands('''
echo $DEPLOYER_PRIV_KEY
echo $VALUE2
''')

assert "12345" in result

print(result)


# ----------------------------

# did noit require any command changes

def monitor_process(proc):
    """Function to run in a separate thread that monitors the process"""
    try:
        # This will block in the thread but not the main program
        proc.expect(pexpect.EOF, timeout=None)
        print("Process has terminated naturally")
    except Exception as e:
        print(f"Exception in monitor thread: {e}")

# run in the background and do not block the main thread
# process = pexpect.spawn('bash -c "while true; do date; sleep 1; done"')
process = pexpect.spawn('''bash -c "echo 'test' > test.txt && ondod start"''')
pid = process.pid
print(f"Process started with PID: {pid}")

# Create and start a monitoring thread
monitor_thread = threading.Thread(target=monitor_process, args=(process,), daemon=True)
monitor_thread.start()

print("Main program continues running...")
# Main program continues running
print("Main program is running...")

# Do stuff in your main program
for i in range(5):
    # Periodically check on the process or read output
    if process.isalive():
        try:
            # Read any available output without blocking
            output = process.read_nonblocking(size=1024, timeout=0.1)
            if output:
                print(f"Got output: {output.decode('utf-8').strip()}")
        except pexpect.TIMEOUT:
            # No output available right now
            pass
        except pexpect.EOF:
            print("Process has ended")
    else:
        print("Process is no longer running")
        break

    print(f"Main program still working... ({i+1}/5)")
    time.sleep(2)

print("Main program work is complete")

# Later, when you want to terminate the process
if process.isalive():
    print(f"Terminating process {pid}...")
    process.terminate(force=True)
    print("Process terminated")

# Wait for the monitor thread to finish
monitor_thread.join(timeout=2)

print("Program exiting")
