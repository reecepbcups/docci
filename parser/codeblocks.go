package parser

import (
	"fmt"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/reecepbcups/docci/logger"
	"github.com/reecepbcups/docci/types"
)

// CodeBlock represents a parsed code block with its metadata
type CodeBlock struct {
	Index           int
	Language        string
	Content         string
	OutputContains  string
	Background      bool
	BackgroundKill  int // 1-based index of background process to kill
	AssertFailure   bool
	OS              string
	WaitForEndpoint string
	WaitTimeoutSecs int
	RetryCount      int
	DelayBeforeSecs float64
	DelayAfterSecs  float64
	DelayPerCmdSecs float64
	IfFileNotExists string
	IfNotInstalled  string
	LineNumber      int
	FileName        string // Added for debugging multiple files
	ReplaceText     string

	// File operation fields
	File        string // docci-file: The file name to operate on
	ResetFile   bool   // docci-reset-file: Reset the file to its original content
	LineInsert  int    // docci-line-insert: Insert content at line N (1-based)
	LineReplace string // docci-line-replace: Replace content at line N or N-M

	content strings.Builder // Used during parsing to build content
}

// given a markdown file, parse out all the code blocks within it.
// Codeblocks are provided as ``` and closed with ```.

var ValidLangs = []string{"bash", "shell", "sh"}

// newCodeBlock creates a new CodeBlock with default values
func newCodeBlock(index int, language string) *CodeBlock {
	return &CodeBlock{
		Index:    index,
		Language: language,
	}
}

// applyTags applies parsed tags to the CodeBlock
func (c *CodeBlock) applyTags(tags MetaTag, lineNumber int, fileName string) {
	c.OutputContains = tags.OutputContains
	c.Background = tags.Background
	c.BackgroundKill = tags.BackgroundKill
	c.AssertFailure = tags.AssertFailure
	c.OS = tags.OS
	c.WaitForEndpoint = tags.WaitForEndpoint
	c.WaitTimeoutSecs = tags.WaitTimeoutSecs
	c.RetryCount = tags.RetryCount
	c.DelayBeforeSecs = tags.DelayBeforeSecs
	c.DelayAfterSecs = tags.DelayAfterSecs
	c.DelayPerCmdSecs = tags.DelayPerCmdSecs
	c.IfFileNotExists = tags.IfFileNotExists
	c.IfNotInstalled = tags.IfNotInstalled
	c.ReplaceText = tags.ReplaceText
	c.File = tags.File
	c.ResetFile = tags.ResetFile
	c.LineInsert = tags.LineInsert
	c.LineReplace = tags.LineReplace
	c.LineNumber = lineNumber
	c.FileName = fileName
	c.content.Reset()
}

// finalize converts the accumulated content from the builder to the Content field
func (c *CodeBlock) finalize() {
	c.Content = c.content.String()
}

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
	var currentBlock *CodeBlock
	lines := splitIntoLines(markdown)
	startParsing := false
	for idx, line := range lines {
		lineNumber := idx + 1 // 1-based index for line numbers

		// stop the parsing when the codeblock ends
		if startParsing {
			if strings.Trim(line, " ") == "```" {
				if currentBlock != nil && currentBlock.content.Len() > 0 {
					// Only add the block if it should run on current OS and command conditions are met
					if ShouldRunOnCurrentOS(currentBlock.OS) && ShouldRunBasedOnCommandInstallation(currentBlock.IfNotInstalled) {
						currentBlock.finalize()
						codeBlocks = append(codeBlocks, *currentBlock)
					} else {
						logger.GetLogger().Debug("Skipping code block due to OS restriction", "required_os", currentBlock.OS, "current_os", GetCurrentOS())
					}
					currentBlock = nil
				}
				startParsing = false
				continue
			}

			// if not, then we add the text to the codeblock
			if currentBlock != nil {
				currentBlock.content.WriteString(line)
				currentBlock.content.WriteString("\n")
				logger.GetLogger().Debug("Adding line to code block", "line_number", lineNumber, "content", line)
			}
		}

		// we only start parsing if the line contains ```bash, ```shell, or ```sh
		// TODO: only run this if startParsing is false?
		if strings.HasPrefix(line, "```") {
			// Parse tags first to check for ignore
			tags, err := ParseTags(line)
			if err != nil {
				return nil, fmt.Errorf("line %d: parse tags: %w", lineNumber, err)
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

			// Allow block if it's a valid language OR if it has file operation tags
			if contains(ValidLangs, lang) || tags.File != "" {
				// Validate tag combinations using the centralized validation
				if err := tags.Validate(lineNumber); err != nil {
					return nil, err
				}

				startParsing = true
				currentBlock = newCodeBlock(len(codeBlocks)+1, lang)
				currentBlock.applyTags(tags, lineNumber, fileName)
				continue
			}
			continue
		}
	}

	// Validate background-kill references
	backgroundIndexes := make(map[int]bool)
	for _, block := range codeBlocks {
		if block.Background {
			backgroundIndexes[block.Index] = true
		}
	}

	// Check all background-kill references
	for _, block := range codeBlocks {
		if block.BackgroundKill > 0 {
			if !backgroundIndexes[block.BackgroundKill] {
				// Find all available background indexes for error message
				var availableIndexes []int
				for idx := range backgroundIndexes {
					availableIndexes = append(availableIndexes, idx)
				}
				sort.Ints(availableIndexes)

				if len(availableIndexes) == 0 {
					return nil, fmt.Errorf("block %d (line %d): docci-background-kill=%d references a non-existent background process. No background processes are defined in this file",
						block.Index, block.LineNumber, block.BackgroundKill)
				} else {
					return nil, fmt.Errorf("block %d (line %d): docci-background-kill=%d references a non-existent background process. Available background process indexes: %v",
						block.Index, block.LineNumber, block.BackgroundKill, availableIndexes)
				}
			}
		}
	}

	return codeBlocks, nil
}

// WaitForEndpoint polls an HTTP endpoint until it's ready or timeout is reached
func WaitForEndpoint(url string, timeoutSecs int) error {
	log := logger.GetLogger()
	log.Info("Waiting for endpoint to be ready", "url", url, "timeout_secs", timeoutSecs)

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
			log.Info("Endpoint is ready", "url", url, "status", resp.StatusCode)
			return nil
		}

		if resp != nil {
			resp.Body.Close()
		}

		log.Debug("Endpoint not ready yet, retrying in 1 second", "url", url)
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
	debugEnabled := logger.IsDebugEnabled()

	// Always generate markers for parsing, visibility controlled in executor

	// Add trap at the beginning to clean up background processes
	// Only set the trap if keepRunning is false
	if !opts.KeepRunning {
		script.WriteString(replaceTemplateVars(scriptCleanupTemplate, map[string]string{
			"DEBUG_CLEANUP": formatDebugCleanup(debugEnabled),
		}))
	}

	var backgroundIndexes []int

	for _, block := range blocks {
		// Handle background kill first if specified
		if block.BackgroundKill > 0 {
			script.WriteString(replaceTemplateVars(backgroundKillTemplate, map[string]string{
				"KILL_INDEX": strconv.Itoa(block.BackgroundKill),
				"FILE_INFO":  formatFileInfo(block.FileName),
			}))
		}

		if block.Background {
			// For background blocks, wrap in { } & and redirect output
			script.WriteString(replaceTemplateVars(backgroundBlockTemplate, map[string]string{
				"INDEX":     strconv.Itoa(block.Index),
				"FILE_INFO": formatFileInfo(block.FileName),
				"CONTENT":   block.Content,
			}))
			backgroundPIDs = append(backgroundPIDs, fmt.Sprintf("$DOCCI_BG_PID_%d", block.Index))
			backgroundIndexes = append(backgroundIndexes, block.Index)
		} else {
			// Regular blocks with markers (always generated for parsing)
			script.WriteString(replaceTemplateVars(blockStartMarkerTemplate, map[string]string{
				"INDEX": strconv.Itoa(block.Index),
			}))

			// Add the block header comment only in debug mode
			if debugEnabled {
				script.WriteString(replaceTemplateVars(blockHeaderTemplate, map[string]string{
					"INDEX":     strconv.Itoa(block.Index),
					"LANGUAGE":  block.Language,
					"FILE_INFO": formatFileInfo(block.FileName),
				}))
			}

			// Add delay before block if specified
			if block.DelayBeforeSecs > 0 {
				script.WriteString(replaceTemplateVars(delayBeforeTemplate, map[string]string{
					"INDEX": strconv.Itoa(block.Index),
					"DELAY": strconv.FormatFloat(block.DelayBeforeSecs, 'g', -1, 64),
				}))
			}

			// Add wait-for-endpoint logic if needed
			if block.WaitForEndpoint != "" {
				script.WriteString(replaceTemplateVars(waitForEndpointTemplate, map[string]string{
					"ENDPOINT": block.WaitForEndpoint,
					"TIMEOUT":  strconv.Itoa(block.WaitTimeoutSecs),
				}))
			}

			// Add file existence check as guard clause if needed
			if block.IfFileNotExists != "" {
				script.WriteString(replaceTemplateVars(fileExistenceGuardStartTemplate, map[string]string{
					"FILE":  block.IfFileNotExists,
					"INDEX": strconv.Itoa(block.Index),
				}))
			}

			// Apply text replacement if needed
			blockContent := block.Content
			if block.ReplaceText != "" {
				parts := strings.SplitN(block.ReplaceText, ";", 2)
				if len(parts) == 2 {
					oldText := parts[0]
					newText := parts[1]
					blockContent = strings.ReplaceAll(blockContent, oldText, newText)
					log.Debug("Applied text replacement", "block", block.Index, "old", oldText, "new", newText)
				}
			}

			// Check if this is a file operation block
			if block.File != "" {
				// Handle file operations
				if block.ResetFile || block.LineInsert == 0 && block.LineReplace == "" {
					// Create or reset file
					operation := "create"
					if block.ResetFile {
						operation = "reset"
					}
					script.WriteString(replaceTemplateVars(fileCreateOrResetTemplate, map[string]string{
						"OPERATION": operation,
						"FILE":      block.File,
						"FILE_INFO": formatFileInfo(block.FileName),
						"CONTENT":   blockContent,
					}))
				} else if block.LineInsert > 0 {
					// Insert at line
					script.WriteString(replaceTemplateVars(fileLineInsertTemplate, map[string]string{
						"FILE":      block.File,
						"LINE":      strconv.Itoa(block.LineInsert),
						"FILE_INFO": formatFileInfo(block.FileName),
						"CONTENT":   blockContent,
					}))
				} else if block.LineReplace != "" {
					// Replace line(s)
					startLine := ""
					endLine := ""

					if strings.Contains(block.LineReplace, "-") {
						parts := strings.Split(block.LineReplace, "-")
						startLine = strings.TrimSpace(parts[0])
						endLine = strings.TrimSpace(parts[1])
					} else {
						startLine = block.LineReplace
						endLine = block.LineReplace
					}

					script.WriteString(replaceTemplateVars(fileLineReplaceTemplate, map[string]string{
						"FILE":       block.File,
						"LINES":      block.LineReplace,
						"START_LINE": startLine,
						"END_LINE":   endLine,
						"FILE_INFO":  formatFileInfo(block.FileName),
						"CONTENT":    blockContent,
					}))
				}
			} else {
				// Regular code execution (not a file operation)
				// Prepare the code content with per-command delay and command display
				delaySeconds := block.DelayPerCmdSecs
				codeContent := replaceTemplateVars(codeExecutionTemplate, map[string]string{
					"DELAY":      strconv.FormatFloat(delaySeconds, 'g', -1, 64),
					"BASH_FLAGS": formatBashFlags(block.AssertFailure),
					"CONTENT":    blockContent,
				})

				// Add the actual code with retry logic if needed
				if block.RetryCount > 0 {
					retryDelay := GetRetryDelay()
					script.WriteString(replaceTemplateVars(retryWrapperStartTemplate, map[string]string{
						"INDEX":       strconv.Itoa(block.Index),
						"MAX_RETRIES": strconv.Itoa(block.RetryCount),
						"RETRY_DELAY": strconv.Itoa(retryDelay),
					}))
					script.WriteString(codeContent)
					script.WriteString(replaceTemplateVars(retryWrapperEndTemplate, map[string]string{
						"INDEX": strconv.Itoa(block.Index),
					}))
				} else {
					script.WriteString(codeContent)
				}
			}

			// Close the guard clause if needed
			if block.IfFileNotExists != "" {
				script.WriteString("fi\n")
			}

			// Add delay after block if specified
			if block.DelayAfterSecs > 0 {
				script.WriteString(replaceTemplateVars(delayAfterTemplate, map[string]string{
					"INDEX": strconv.Itoa(block.Index),
					"DELAY": strconv.FormatFloat(block.DelayAfterSecs, 'g', -1, 64),
				}))
			}

			// Add a marker after the block
			script.WriteString(replaceTemplateVars(blockEndMarkerTemplate, map[string]string{
				"INDEX": strconv.Itoa(block.Index),
			}))

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
		var logEntries strings.Builder
		for _, bgIndex := range backgroundIndexes {
			logEntries.WriteString(replaceTemplateVars(backgroundLogEntryTemplate, map[string]string{
				"INDEX": strconv.Itoa(bgIndex),
			}))
		}
		script.WriteString(replaceTemplateVars(backgroundLogsDisplayTemplate, map[string]string{
			"LOG_ENTRIES": logEntries.String(),
		}))
	} else if len(backgroundIndexes) > 0 && opts.HideBackgroundLogs {
		// Still clean up the background output files even if we're not displaying them
		var cleanupCommands strings.Builder
		for _, bgIndex := range backgroundIndexes {
			cleanupCommands.WriteString(fmt.Sprintf("rm -f /tmp/docci_bg_%d.out\n", bgIndex))
		}
		script.WriteString(replaceTemplateVars(backgroundLogsCleanupTemplate, map[string]string{
			"CLEANUP_COMMANDS": cleanupCommands.String(),
		}))
	}

	// Add infinite sleep if keepRunning is true (as a final block)
	if opts.KeepRunning {
		script.WriteString(replaceTemplateVars(keepRunningTemplate, map[string]string{
			"DEBUG_CLEANUP": formatDebugCleanup(debugEnabled),
		}))
	}

	return script.String(), validationMap, assertFailureMap
}
