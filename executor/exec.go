package executor

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"

	"github.com/reecepbcups/docci/logger"
)

type ExecResponse struct {
	ExitCode uint
	Error    error // only if ExitCode != 0
	Stdout   string
	Stderr   string
}

func NewExecResponse(exitCode uint, stdout, stderr string, err error) ExecResponse {
	return ExecResponse{
		ExitCode: exitCode,
		Error:    err,
		Stdout:   stdout,
		Stderr:   stderr,
	}
}

// Exec runs a specific codeblock in a bash shell.
// returns exit (status code, error message)

func Exec(commands string) ExecResponse {
	log := logger.GetLogger()
	log.Debug("Executing commands in bash shell")

	cmd := exec.Command("bash", "-c", commands)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		panic(err)
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		panic(err)
	}

	if err := cmd.Start(); err != nil {
		panic(err)
	}

	var stdoutBuf, stderrBuf strings.Builder // captures output for further validation
	var mu sync.Mutex // For thread-safe string builder access

	// Create goroutines to read both stdout and stderr concurrently
	done := make(chan bool, 2)

	// Handle stdout
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if line != "" {
				// Don't print DOCCI markers and cleanup messages to stdout
				shouldPrint := true

				if strings.Contains(line, "DOCCI_BLOCK_START_") || strings.Contains(line, "DOCCI_BLOCK_END_") {
					shouldPrint = false
				}
				if strings.Contains(line, "Cleaning up background processes") {
					shouldPrint = false
				}
				// Don't show "=== Code Block" headers
				if strings.Contains(line, "=== Code Block") {
					shouldPrint = false
				}

				if shouldPrint {
					io.WriteString(os.Stdout, line+"\n")
				}
				// Always capture in buffer for validation
				mu.Lock()
				stdoutBuf.WriteString(line + "\n")
				mu.Unlock()
			}
		}
		done <- true
	}()

	// Handle stderr
	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			line := scanner.Text()
			if line != "" {

				// TODO: DevEx:
				// if error like `bash: -c: line 3: unexpected EOF while looking for matching `"'`
				// show the actual line number in the file / code block section to help debug.
				// This case above is when you forget to add a closing quote to an echo line.

				io.WriteString(os.Stderr, line+"\n")
				mu.Lock()
				stderrBuf.WriteString(line + "\n")
				mu.Unlock()
			}
		}
		done <- true
	}()

	// Wait for both goroutines to finish
	<-done
	<-done

	if err := cmd.Wait(); err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			exitCode := exitError.ExitCode()
			exitErr := exitError.Error()
			log.Debugf("Command exited with code: %d, error: %s", exitCode, exitErr)
			return NewExecResponse(uint(exitCode), stdoutBuf.String(), stderrBuf.String(), fmt.Errorf(exitError.Error()))
		} else {
			panic(err)
		}
	}

	log.Debug("Command executed successfully")
	return NewExecResponse(0, stdoutBuf.String(), stderrBuf.String(), nil)
}

// ParseBlockOutputs extracts output for each code block based on markers
func ParseBlockOutputs(output string) map[int]string {
	log := logger.GetLogger()
	log.Debug("Parsing block outputs from execution result")
	blockOutputs := make(map[int]string)
	lines := strings.Split(output, "\n")

	var currentBlock int
	var currentOutput strings.Builder
	inBlock := false

	for _, line := range lines {
		// Check for start marker
		if strings.HasPrefix(line, "### DOCCI_BLOCK_START_") && strings.HasSuffix(line, " ###") {
			// Extract block number
			marker := strings.TrimPrefix(line, "### DOCCI_BLOCK_START_")
			marker = strings.TrimSuffix(marker, " ###")
			fmt.Sscanf(marker, "%d", &currentBlock)
			log.Debugf("Found start marker for block %d", currentBlock)
			inBlock = true
			currentOutput.Reset()
			continue
		}

		// Check for end marker
		if strings.HasPrefix(line, "### DOCCI_BLOCK_END_") && strings.HasSuffix(line, " ###") {
			if inBlock {
				blockOutputs[currentBlock] = strings.TrimSpace(currentOutput.String())
				log.Debugf("Found end marker for block %d, captured output length: %d", currentBlock, len(blockOutputs[currentBlock]))
			}
			inBlock = false
			continue
		}

		// Skip code block headers
		if strings.HasPrefix(line, "### === Code Block") {
			continue
		}

		// Collect output if we're in a block
		if inBlock {
			if currentOutput.Len() > 0 {
				currentOutput.WriteString("\n")
			}
			currentOutput.WriteString(line)
		}
	}

	log.Debugf("Parsed %d block outputs", len(blockOutputs))
	return blockOutputs
}

// ValidateOutputs checks if block outputs contain expected strings
func ValidateOutputs(blockOutputs map[int]string, validationMap map[int]string) []error {
	log := logger.GetLogger()
	log.Debug("Validating block outputs against expected strings")
	var errors []error

	for blockIndex, expectedContains := range validationMap {
		output, exists := blockOutputs[blockIndex]
		if !exists {
			log.Errorf("No output found for block %d", blockIndex)
			errors = append(errors, fmt.Errorf("no output found for block %d", blockIndex))
			continue
		}

		if !strings.Contains(output, expectedContains) {
			log.Errorf("Block %d validation failed: output does not contain '%s'", blockIndex, expectedContains)
			errors = append(errors, fmt.Errorf("block %d: output does not contain expected string '%s'\nActual output:\n%s",
				blockIndex, expectedContains, output))
		} else {
			log.Debugf("Block %d validation passed: found expected string '%s'", blockIndex, expectedContains)
		}
	}

	return errors
}
