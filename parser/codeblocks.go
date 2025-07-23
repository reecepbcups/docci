package parser

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/reecepbcups/docci/logger"
	"github.com/reecepbcups/docci/types"
	"github.com/sirupsen/logrus"
)

// CodeBlock represents a parsed code block with its metadata
type CodeBlock struct {
	Index           int
	Language        string
	Content         string
	OutputContains  string
	Background      bool
	AssertFailure   bool
	OS              string
	WaitForEndpoint string
	WaitTimeoutSecs int
	RetryCount      int
	DelayBeforeSecs float64
	DelayAfterSecs  float64
	DelayPerCmdSecs float64
	IfFileNotExists string
	LineNumber      int
	FileName        string // Added for debugging multiple files
	ReplaceText     string
}

// given a markdown file, parse out all the code blocks within it.
// Codeblocks are provided as ``` and closed with ```.

var ValidLangs = []string{"bash", "shell", "sh"}

// GetRetryDelay returns the retry delay in seconds from environment variable or default
func GetRetryDelay() int {
	if delayStr := os.Getenv("DOCCI_RETRY_DELAY"); delayStr != "" {
		if delay, err := strconv.Atoi(delayStr); err == nil && delay >= 0 {
			return delay
		}
	}
	return 2 // Default 2 seconds
}

// ParseCodeBlocksWithMetadata returns structured code blocks with metadata
func ParseCodeBlocks(markdown string) ([]CodeBlock, error) {
	return ParseCodeBlocksWithFileName(markdown, "")
}

// ParseCodeBlocksWithFileName returns structured code blocks with metadata and filename
func ParseCodeBlocksWithFileName(markdown string, fileName string) ([]CodeBlock, error) {
	var codeBlocks []CodeBlock
	state := newCodeBlockState()
	lines := splitIntoLines(markdown)
	startParsing := false
	for idx, line := range lines {
		lineNumber := idx + 1 // 1-based index for line numbers

		// stop the parsing when the codeblock ends
		if startParsing {
			if strings.Trim(line, " ") == "```" {
				if state.content.Len() > 0 {
					// Only add the block if it should run on current OS and command conditions are met
					if ShouldRunOnCurrentOS(state.os) && ShouldRunBasedOnCommandInstallation(state.ifNotInstalled) {
						codeBlocks = append(codeBlocks, state.toCodeBlock(len(codeBlocks)+1, fileName))
					} else {
						logger.GetLogger().Debugf("Skipping code block due to OS restriction: block requires '%s', current OS is '%s'", state.os, GetCurrentOS())
					}
					state.reset()
				}
				startParsing = false
				continue
			}

			// if not, then we add the text to the codeblock
			state.content.WriteString(line)
			state.content.WriteString("\n")
			logger.GetLogger().Debugf("Adding line %d to code block: %s", lineNumber, line)
		}

		// we only start parsing if the line contains ```bash, ```shell, or ```sh
		// TODO: only run this if startParsing is false?
		if strings.HasPrefix(line, "```") {
			// Parse tags first to check for ignore
			tags, err := ParseTags(line)
			if err != nil {
				logger.GetLogger().Errorf("Error parsing tags on line %d: %v", lineNumber, err)
				continue
			}

			if tags.Ignore {
				logger.GetLogger().Debug("Ignoring code block due to docci-ignore tag")
				continue
			}

			// Extract just the language part (before any tags)
			lang := strings.TrimPrefix(line, "```")
			lang = strings.TrimSpace(lang)
			// Split by space to get just the language part
			langParts := strings.Fields(lang)
			if len(langParts) > 0 {
				lang = langParts[0]
			}

			if contains(ValidLangs, lang) {
				// Validate tag combinations
				if tags.OutputContains != "" && tags.Background {
					return nil, fmt.Errorf("line %d: Cannot use both docci-output-contains and docci-background on the same code block", lineNumber)
				}
				if tags.AssertFailure && tags.Background {
					return nil, fmt.Errorf("line %d: Cannot use both docci-assert-failure and docci-background on the same code block", lineNumber)
				}
				if tags.AssertFailure && tags.OutputContains != "" {
					return nil, fmt.Errorf("line %d: Cannot use both docci-assert-failure and docci-output-contains on the same code block", lineNumber)
				}
				if tags.WaitForEndpoint != "" && tags.Background {
					return nil, fmt.Errorf("line %d: Cannot use both docci-wait-for-endpoint and docci-background on the same code block", lineNumber)
				}
				if tags.RetryCount > 0 && tags.Background {
					return nil, fmt.Errorf("line %d: Cannot use both docci-retry and docci-background on the same code block", lineNumber)
				}

				startParsing = true
				state.applyTags(tags, lang, lineNumber)
				continue
			}
			continue
		}
	}

	return codeBlocks, nil
}

// WaitForEndpoint polls an HTTP endpoint until it's ready or timeout is reached
func WaitForEndpoint(url string, timeoutSecs int) error {
	log := logger.GetLogger()
	log.Infof("Waiting for endpoint %s to be ready (timeout: %d seconds)", url, timeoutSecs)

	timeout := time.Duration(timeoutSecs) * time.Second
	client := &http.Client{
		Timeout: 5 * time.Second, // 5 second timeout per request
	}

	start := time.Now()
	for {
		if time.Since(start) >= timeout {
			return fmt.Errorf("timeout waiting for endpoint %s after %d seconds", url, timeoutSecs)
		}

		resp, err := client.Get(url)
		if err == nil && resp.StatusCode >= 200 && resp.StatusCode < 300 {
			resp.Body.Close()
			log.Infof("Endpoint %s is ready (status: %d)", url, resp.StatusCode)
			return nil
		}

		if resp != nil {
			resp.Body.Close()
		}

		log.Debugf("Endpoint %s not ready yet (attempt failed), retrying in 1 second...", url)
		time.Sleep(1 * time.Second)
	}
}

// BuildExecutableScript creates a single script with validation markers
func BuildExecutableScript(blocks []CodeBlock) (string, map[int]string, map[int]bool) {
	return BuildExecutableScriptWithOptions(blocks, types.DocciOpts{
		HideBackgroundLogs: false,
		KeepRunning:        false,
	})
}

// BuildExecutableScriptWithOptions creates a single script with validation markers and options
func BuildExecutableScriptWithOptions(blocks []CodeBlock, opts types.DocciOpts) (string, map[int]string, map[int]bool) {
	log := logger.GetLogger()
	var script strings.Builder
	validationMap := make(map[int]string)  // maps block index to expected output
	assertFailureMap := make(map[int]bool) // maps block index to assert-failure flag
	var backgroundPIDs []string

	// Always generate markers for parsing, visibility controlled in executor

	// Add trap at the beginning to clean up background processes
	// Only set the trap if keepRunning is false
	if !opts.KeepRunning {
		script.WriteString("# Cleanup function for background processes\n")
		script.WriteString("cleanup_background_processes() {\n")
		// higher numbers are actually more verbose in the logrus library
		if log.Level >= logrus.DebugLevel {
			script.WriteString("  echo 'Cleaning up background processes...'\n")
		}
		script.WriteString("  jobs -p | xargs -r kill 2>/dev/null\n")
		script.WriteString("}\n")
		script.WriteString("trap cleanup_background_processes EXIT\n\n")
	}

	var backgroundIndexes []int

	for _, block := range blocks {
		if block.Background {
			// For background blocks, wrap in { } & and redirect output
			fileInfo := ""
			if block.FileName != "" {
				fileInfo = fmt.Sprintf(" from %s", block.FileName)
			}
			script.WriteString(fmt.Sprintf("# Background block %d%s\n", block.Index, fileInfo))
			script.WriteString("{\n")
			script.WriteString(block.Content)
			script.WriteString(fmt.Sprintf("} > /tmp/docci_bg_%d.out 2>&1 &\n", block.Index))
			script.WriteString(fmt.Sprintf("DOCCI_BG_PID_%d=$!\n", block.Index))
			script.WriteString(fmt.Sprintf("echo 'Started background process %d with PID '$DOCCI_BG_PID_%d\n\n", block.Index, block.Index))
			backgroundPIDs = append(backgroundPIDs, fmt.Sprintf("$DOCCI_BG_PID_%d", block.Index))
			backgroundIndexes = append(backgroundIndexes, block.Index)
		} else {
			// Regular blocks with markers (always generated for parsing)
			marker := fmt.Sprintf("### DOCCI_BLOCK_START_%d ###", block.Index)
			script.WriteString(fmt.Sprintf("echo '%s'\n", marker))

			// Add the block header comment only in debug mode
			if log.Level >= logrus.DebugLevel {
				fileInfo := ""
				if block.FileName != "" {
					fileInfo = fmt.Sprintf(" from %s", block.FileName)
				}
				script.WriteString(fmt.Sprintf("### === Code Block %d (%s)%s ===\n", block.Index, block.Language, fileInfo))
			}

			// Add delay before block if specified
			if block.DelayBeforeSecs > 0 {
				script.WriteString(fmt.Sprintf("# Delay before block %d for %g seconds\n", block.Index, block.DelayBeforeSecs))
				script.WriteString(fmt.Sprintf("sleep %g\n", block.DelayBeforeSecs))
			}

			// Add wait-for-endpoint logic if needed
			if block.WaitForEndpoint != "" {
				script.WriteString(fmt.Sprintf("# Waiting for endpoint %s (timeout: %d seconds)\n", block.WaitForEndpoint, block.WaitTimeoutSecs))
				script.WriteString(fmt.Sprintf("echo 'Waiting for endpoint %s to be ready...'\n", block.WaitForEndpoint))
				script.WriteString(fmt.Sprintf(`
timeout_secs=%d
endpoint_url="%s"
start_time=$(date +%%s)

while true; do
    current_time=$(date +%%s)
    elapsed=$((current_time - start_time))

    if [ $elapsed -ge $timeout_secs ]; then
        echo "Timeout waiting for endpoint $endpoint_url after $timeout_secs seconds"
        exit 1
    fi

    if curl -s -f --max-time 5 "$endpoint_url" > /dev/null 2>&1; then
        echo "Endpoint $endpoint_url is ready"
        break
    fi

    echo "Endpoint not ready yet, retrying in 1 second... (elapsed: ${elapsed}s)"
    sleep 1
done

`, block.WaitTimeoutSecs, block.WaitForEndpoint))
			}

			// Add file existence check as guard clause if needed
			if block.IfFileNotExists != "" {
				script.WriteString(fmt.Sprintf("# Guard clause: check if file exists and skip if it does\n"))
				script.WriteString(fmt.Sprintf("if [ -f \"%s\" ]; then\n", block.IfFileNotExists))
				script.WriteString(fmt.Sprintf("  echo \"Skipping block %d: file %s already exists\"\n", block.Index, block.IfFileNotExists))
				script.WriteString("else\n")
				script.WriteString(fmt.Sprintf("  echo \"File %s does not exist, executing block %d\"\n", block.IfFileNotExists, block.Index))
				script.WriteString("fi\n")
				script.WriteString(fmt.Sprintf("if [ ! -f \"%s\" ]; then\n", block.IfFileNotExists))
			}

			// Apply text replacement if needed
			blockContent := block.Content
			if block.ReplaceText != "" {
				parts := strings.SplitN(block.ReplaceText, ";", 2)
				if len(parts) == 2 {
					oldText := parts[0]
					newText := parts[1]
					blockContent = strings.ReplaceAll(blockContent, oldText, newText)
					log.Debugf("Applied text replacement in block %d: '%s' -> '%s'", block.Index, oldText, newText)
				}
			}

			// Prepare the code content with per-command delay and command display
			delaySeconds := block.DelayPerCmdSecs
			bashFlags := "-eT"
			if block.AssertFailure {
				bashFlags = "-T" // Don't use -e for assert-failure blocks
			}
			codeContent := fmt.Sprintf(`# Enable per-command delay (%g seconds) and command display
set %s
trap 'echo -e "\n     Executing CMD: $BASH_COMMAND" >&2; sleep %g' DEBUG

%s

# Disable trap
trap - DEBUG
`, delaySeconds, bashFlags, delaySeconds, blockContent)

			// Add the actual code with retry logic if needed
			if block.RetryCount > 0 {
				retryDelay := GetRetryDelay()
				script.WriteString(fmt.Sprintf("# Retry logic for block %d (max attempts: %d)\n", block.Index, block.RetryCount))
				script.WriteString("retry_count=0\n")
				script.WriteString(fmt.Sprintf("max_retries=%d\n", block.RetryCount))
				script.WriteString("while [ $retry_count -le $max_retries ]; do\n")
				script.WriteString("  if [ $retry_count -gt 0 ]; then\n")
				script.WriteString(fmt.Sprintf("    echo \"Retry attempt $retry_count/$max_retries for block %d\"\n", block.Index))
				if retryDelay > 0 {
					script.WriteString(fmt.Sprintf("    sleep %d\n", retryDelay))
				}
				script.WriteString("  fi\n")
				script.WriteString("  \n")
				script.WriteString("  # Execute the block content\n")
				script.WriteString("  if (\n")
				script.WriteString(codeContent)
				script.WriteString("  ); then\n")
				script.WriteString("    break\n")
				script.WriteString("  else\n")
				script.WriteString("    exit_code=$?\n")
				script.WriteString("    retry_count=$((retry_count + 1))\n")
				script.WriteString("    if [ $retry_count -gt $max_retries ]; then\n")
				script.WriteString(fmt.Sprintf("      echo \"Block %d failed after $max_retries retry attempts\"\n", block.Index))
				script.WriteString("      exit $exit_code\n")
				script.WriteString("    fi\n")
				script.WriteString("  fi\n")
				script.WriteString("done\n")
			} else {
				script.WriteString(codeContent)
			}

			// Close the guard clause if needed
			if block.IfFileNotExists != "" {
				script.WriteString("fi\n")
			}

			// Add delay after block if specified
			if block.DelayAfterSecs > 0 {
				script.WriteString(fmt.Sprintf("# Delay after block %d for %g seconds\n", block.Index, block.DelayAfterSecs))
				script.WriteString(fmt.Sprintf("sleep %g\n", block.DelayAfterSecs))
			}

			// Add a marker after the block
			endMarker := fmt.Sprintf("### DOCCI_BLOCK_END_%d ###", block.Index)
			script.WriteString(fmt.Sprintf("echo '%s'\n", endMarker))

			// Store validation requirement if present
			if block.OutputContains != "" {
				validationMap[block.Index] = block.OutputContains
			}
			// Store assert-failure requirement if present
			if block.AssertFailure {
				assertFailureMap[block.Index] = true
			}
		}
	}

	// Add section to display background logs at the end (unless hidden)
	if len(backgroundIndexes) > 0 && !opts.HideBackgroundLogs {
		script.WriteString("\n# Display background process logs\n")
		script.WriteString("echo -e '\\n=== Background Process Logs ==='\n")
		for _, bgIndex := range backgroundIndexes {
			script.WriteString(fmt.Sprintf("if [ -f /tmp/docci_bg_%d.out ]; then\n", bgIndex))
			script.WriteString(fmt.Sprintf("  echo -e '\\n--- Background Block %d Output ---'\n", bgIndex))
			script.WriteString(fmt.Sprintf("  cat /tmp/docci_bg_%d.out\n", bgIndex))
			script.WriteString(fmt.Sprintf("  rm -f /tmp/docci_bg_%d.out\n", bgIndex))
			script.WriteString("else\n")
			script.WriteString(fmt.Sprintf("  echo 'No output file found for background block %d'\n", bgIndex))
			script.WriteString("fi\n")
		}
	} else if len(backgroundIndexes) > 0 && opts.HideBackgroundLogs {
		// Still clean up the background output files even if we're not displaying them
		script.WriteString("\n# Clean up background process logs (hidden)\n")
		for _, bgIndex := range backgroundIndexes {
			script.WriteString(fmt.Sprintf("rm -f /tmp/docci_bg_%d.out\n", bgIndex))
		}
	}

	// Add infinite sleep if keepRunning is true (as a final block)
	if opts.KeepRunning {
		script.WriteString("\n# Keep containers running with infinite sleep\n")
		script.WriteString("echo '\\n🔄 Keeping containers running. Press Ctrl+C to stop...'\n")

		// Add trap for cleanup when keepRunning is true
		script.WriteString("\n# Cleanup function for background processes (on interrupt)\n")
		script.WriteString("cleanup_on_interrupt() {\n")
		// higher numbers are actually more verbose in the logrus library
		if log.Level >= logrus.DebugLevel {
			script.WriteString("  echo 'Cleaning up background processes...'\n")
		}
		script.WriteString("  jobs -p | xargs -r kill 2>/dev/null\n")
		script.WriteString("  exit 0\n")
		script.WriteString("}\n")
		script.WriteString("trap cleanup_on_interrupt INT TERM\n\n")

		script.WriteString("sleep infinity\n")
	}

	return script.String(), validationMap, assertFailureMap
}
