package parser

// Script templates for bash code generation
const (
	// Main script template with cleanup trap
	scriptCleanupTemplate = `# Cleanup function for background processes
cleanup_background_processes() {
{{DEBUG_CLEANUP}} jobs -p | xargs -r kill 2>/dev/null
}
trap cleanup_background_processes EXIT

`

	// Background kill template
	backgroundKillTemplate = `# Kill background process at index {{KILL_INDEX}}{{FILE_INFO}}
if [ -n "$DOCCI_BG_PID_{{KILL_INDEX}}" ]; then
  echo 'Killing background process {{KILL_INDEX}} with PID '$DOCCI_BG_PID_{{KILL_INDEX}}
  # Kill the entire process group
  kill -TERM -$DOCCI_BG_PID_{{KILL_INDEX}} 2>/dev/null || kill $DOCCI_BG_PID_{{KILL_INDEX}} 2>/dev/null || true
  wait $DOCCI_BG_PID_{{KILL_INDEX}} 2>/dev/null || true
  unset DOCCI_BG_PID_{{KILL_INDEX}}
else
  echo 'Warning: No background process found at index {{KILL_INDEX}}'
fi

`

	// Background block template
	backgroundBlockTemplate = `# Background block {{INDEX}}{{FILE_INFO}}
(
{{CONTENT}}) > /tmp/docci_bg_{{INDEX}}.out 2>&1 &
DOCCI_BG_PID_{{INDEX}}=$!
echo 'Started background process {{INDEX}} with PID '$DOCCI_BG_PID_{{INDEX}}

`

	// Regular block start marker
	blockStartMarkerTemplate = `echo '### DOCCI_BLOCK_START_{{INDEX}} ###'
`

	// Block header (debug mode only)
	blockHeaderTemplate = `### === Code Block {{INDEX}} ({{LANGUAGE}}){{FILE_INFO}} ===
`

	// Delay before template
	delayBeforeTemplate = `# Delay before block {{INDEX}} for {{DELAY}} seconds
sleep {{DELAY}}
`

	// Wait for endpoint template
	waitForEndpointTemplate = `# Waiting for endpoint {{ENDPOINT}} (timeout: {{TIMEOUT}} seconds)
echo 'Waiting for endpoint {{ENDPOINT}} to be ready...'

timeout_secs={{TIMEOUT}}
endpoint_url="{{ENDPOINT}}"
start_time=$(date +%s)

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    if [ $elapsed -ge $timeout_secs ]; then
        echo "Timeout waiting for endpoint $endpoint_url after $timeout_secs seconds"
        exit 1
    fi

    if wget -q --timeout=5 --tries=1 --spider "$endpoint_url" > /dev/null 2>&1; then
        echo "Endpoint $endpoint_url is ready"
        break
    fi

    echo "Endpoint not ready yet, retrying in 1 second... (elapsed: ${elapsed}s)"
    sleep 1
done

`

	// File existence guard template
	fileExistenceGuardStartTemplate = `# Guard clause: check if file exists and skip if it does
if [ -f "{{FILE}}" ]; then
  echo "Skipping block {{INDEX}}: file {{FILE}} already exists"
else
  echo "File {{FILE}} does not exist, executing block {{INDEX}}"
fi
if [ ! -f "{{FILE}}" ]; then
`

	// Code execution with per-command delay template
	codeExecutionTemplate = `# Enable per-command delay ({{DELAY}} seconds) and command display
set {{BASH_FLAGS}}
trap 'echo -e "\n     Executing CMD: $BASH_COMMAND" >&2; sleep {{DELAY}}' DEBUG

{{CONTENT}}

# Disable trap
trap - DEBUG
`

	// Retry wrapper start template
	retryWrapperStartTemplate = `# Retry logic for block {{INDEX}} (max attempts: {{MAX_RETRIES}})
retry_count=0
max_retries={{MAX_RETRIES}}
while [ $retry_count -le $max_retries ]; do
  if [ $retry_count -gt 0 ]; then
    echo "Retry attempt $retry_count/$max_retries for block {{INDEX}}"
    sleep {{RETRY_DELAY}}
  fi

  # Execute the block content
  if (
`

	// Retry wrapper end template
	retryWrapperEndTemplate = `  ); then
    break
  else
    exit_code=$?
    retry_count=$((retry_count + 1))
    if [ $retry_count -gt $max_retries ]; then
      echo "Block {{INDEX}} failed after $max_retries retry attempts"
      exit $exit_code
    fi
  fi
done
`

	// Delay after template
	delayAfterTemplate = `# Delay after block {{INDEX}} for {{DELAY}} seconds
sleep {{DELAY}}
`

	// Block end marker
	blockEndMarkerTemplate = `echo '### DOCCI_BLOCK_END_{{INDEX}} ###'
`

	// Background logs display template
	backgroundLogsDisplayTemplate = `
# Display background process logs
echo -e '\n=== Background Process Logs ==='
{{LOG_ENTRIES}}`

	// Single background log entry template
	backgroundLogEntryTemplate = `if [ -f /tmp/docci_bg_{{INDEX}}.out ]; then
  echo -e '\n--- Background Block {{INDEX}} Output ---'
  cat /tmp/docci_bg_{{INDEX}}.out
  rm -f /tmp/docci_bg_{{INDEX}}.out
else
  echo 'No output file found for background block {{INDEX}}'
fi
`

	// Background logs cleanup template (hidden)
	backgroundLogsCleanupTemplate = `
# Clean up background process logs (hidden)
{{CLEANUP_COMMANDS}}`

	// Keep running template
	keepRunningTemplate = `
# Keep containers running with infinite sleep
echo '\n🔄 Keeping containers running. Press Ctrl+C to stop...'

# Cleanup function for background processes (on interrupt)
cleanup_on_interrupt() {
{{DEBUG_CLEANUP}}  jobs -p | xargs -r kill 2>/dev/null
  exit 0
}
trap cleanup_on_interrupt INT TERM

sleep infinity
`

	// File operation templates
	fileCreateOrResetTemplate = `# File operation: {{OPERATION}} {{FILE}}{{FILE_INFO}}
cat > "{{FILE}}" << 'DOCCI_EOF'
{{CONTENT}}DOCCI_EOF
`

	fileLineInsertTemplate = `# File operation: insert at line {{LINE}} in {{FILE}}{{FILE_INFO}}
if [ -f "{{FILE}}" ]; then
  # Create a temporary file
  temp_file=$(mktemp)

  # Read existing content and insert at specified line
  line_count=0
  inserted=false
  while IFS= read -r line || [ -n "$line" ]; do
    line_count=$((line_count + 1))
    if [ $line_count -eq {{LINE}} ] && [ "$inserted" = "false" ]; then
      cat << 'DOCCI_EOF' >> "$temp_file"
{{CONTENT}}DOCCI_EOF
      inserted=true
    fi
    printf '%s\n' "$line" >> "$temp_file"
  done < "{{FILE}}"

  # If insert line is beyond EOF, append at the end
  total_lines=$line_count
  if [ {{LINE}} -gt $total_lines ] && [ "$inserted" = "false" ]; then
    cat << 'DOCCI_EOF' >> "$temp_file"
{{CONTENT}}DOCCI_EOF
  fi

  # Replace original file
  mv "$temp_file" "{{FILE}}"
else
  echo "Error: File {{FILE}} does not exist for line insert operation"
  exit 1
fi
`

	fileLineReplaceTemplate = `# File operation: replace line(s) {{LINES}} in {{FILE}}{{FILE_INFO}}
if [ -f "{{FILE}}" ]; then
  # Create a temporary file
  temp_file=$(mktemp)

  # Parse line range
  start_line={{START_LINE}}
  end_line={{END_LINE}}

  # Read and replace lines
  line_count=0
  replaced=false
  while IFS= read -r line || [ -n "$line" ]; do
    line_count=$((line_count + 1))
    if [ $line_count -ge $start_line ] && [ $line_count -le $end_line ]; then
      if [ "$replaced" = "false" ]; then
        cat << 'DOCCI_EOF' >> "$temp_file"
{{CONTENT}}DOCCI_EOF
        replaced=true
      fi
      # Skip the lines being replaced
    else
      printf '%s\n' "$line" >> "$temp_file"
    fi
  done < "{{FILE}}"

  # Replace original file
  mv "$temp_file" "{{FILE}}"
else
  echo "Error: File {{FILE}} does not exist for line replace operation"
  exit 1
fi
`
)
