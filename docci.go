package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/reecepbcups/docci/executor"
	"github.com/reecepbcups/docci/logger"
	"github.com/reecepbcups/docci/parser"
)

// DocciResult contains the complete result of running a docci file
type DocciResult struct {
	Success          bool
	ExitCode         int
	Stdout           string
	Stderr           string
	ValidationErrors []error
}

// RunDocciFile executes all the logic for processing a docci markdown file
// This function encapsulates the complete workflow: parse -> build -> execute -> validate
func RunDocciFile(filePath string) DocciResult {
	return RunDocciFileWithOptions(filePath, false)
}

// RunDocciFileWithOptions executes all the logic for processing a docci markdown file with options
func RunDocciFileWithOptions(filePath string, hideBackgroundLogs bool) DocciResult {
	log := logger.GetLogger()

	// Read the file into a string
	log.Debugf("Reading file: %s", filePath)
	markdown, err := os.ReadFile(filePath)
	if err != nil {
		log.Errorf("Failed to read file: %s", err.Error())
		return DocciResult{
			Success:  false,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("Error reading file: %s", err.Error()),
		}
	}

	// Parse code blocks with metadata
	log.Debug("Parsing code blocks from markdown")
	blocks, err := parser.ParseCodeBlocks(string(markdown))
	if err != nil {
		log.Errorf("Failed to parse code blocks: %s", err.Error())
		return DocciResult{
			Success:  false,
			ExitCode: 1,
			Stderr:   fmt.Sprintf("Error parsing code blocks: %s", err.Error()),
		}
	}

	log.Debugf("Found %d code blocks", len(blocks))

	// Build executable script with validation markers
	log.Debug("Building executable script")
	script, validationMap, assertFailureMap := parser.BuildExecutableScriptWithOptions(blocks, hideBackgroundLogs)

	// Execute the script
	log.Debug("Executing script")
	resp := executor.Exec(script)

	// Check assert-failure blocks
	if len(assertFailureMap) > 0 {
		log.Debug("Checking assert-failure expectations")
		// If we have assert-failure blocks, we expect the script to fail
		if resp.Error == nil {
			log.Error("Expected script to fail due to assert-failure tag, but it succeeded")
			return DocciResult{
				Success:  false,
				ExitCode: 1,
				Stdout:   resp.Stdout,
				Stderr:   "Error: Expected script to fail with non-zero exit code due to docci-assert-failure tag, but it succeeded",
			}
		}
		log.Info("✓ Code block failed as expected due to docci-assert-failure tag")
		// Script failed as expected, continue processing
	} else if resp.Error != nil {
		// No assert-failure blocks, so error is unexpected
		log.Errorf("✗ Unexpected script execution failure: %s", resp.Error.Error())
		return DocciResult{
			Success:  false,
			ExitCode: 1,
			Stdout:   resp.Stdout,
			Stderr:   fmt.Sprintf("Error executing code block: %s", resp.Error.Error()),
		}
	}

	// Parse block outputs from the stdout
	log.Debug("Parsing block outputs")
	blockOutputs := executor.ParseBlockOutputs(resp.Stdout)

	// Validate outputs if there are any validation requirements
	var validationErrors []error
	if len(validationMap) > 0 {
		log.Debugf("Validating %d output expectations", len(validationMap))
		validationErrors = executor.ValidateOutputs(blockOutputs, validationMap)
		if len(validationErrors) > 0 {
			log.Errorf("Found %d validation errors", len(validationErrors))
			errorMsg := "\n=== Validation Errors ===\n"
			for _, err := range validationErrors {
				errorMsg += fmt.Sprintf("❌ %s\n", err.Error())
			}
			return DocciResult{
				Success:          false,
				ExitCode:         1,
				Stdout:           resp.Stdout,
				Stderr:           errorMsg,
				ValidationErrors: validationErrors,
			}
		}
		log.Debug("All validations passed")
	}

	log.Debug("Script execution completed successfully")
	return DocciResult{
		Success:          true,
		ExitCode:         0,
		Stdout:           resp.Stdout,
		Stderr:           resp.Stderr,
		ValidationErrors: nil,
	}
}

// RunDocciCommand runs a docci file and handles output/exit like the main function
func RunDocciCommand(filePath string) {
	result := RunDocciFile(filePath)

	// Stderr is already printed in real-time by executor
	// No need to print again

	log := logger.GetLogger()

	// Print success message for validations if applicable
	if result.Success && len(result.ValidationErrors) == 0 {
		// Check if there were any validations that passed
		markdown, _ := os.ReadFile(filePath)
		blocks, _ := parser.ParseCodeBlocks(string(markdown))
		hasValidations := false
		for _, block := range blocks {
			if block.OutputContains != "" || block.AssertFailure {
				hasValidations = true
				break
			}
		}
		if hasValidations {
			log.Info("\n=== All validations passed ✓ ===")
		}
	}

	// Exit with the appropriate code
	if !result.Success {
		os.Exit(result.ExitCode)
	}
}

// RunDocciFiles merges multiple markdown files and executes them as one
func RunDocciFiles(filePaths []string) DocciResult {
	return RunDocciFilesWithOptions(filePaths, false)
}

// RunDocciFilesWithOptions merges multiple markdown files and executes them as one with options
func RunDocciFilesWithOptions(filePaths []string, hideBackgroundLogs bool) DocciResult {
	log := logger.GetLogger()

	log.Debugf("Merging %d markdown files", len(filePaths))

	var allBlocks []parser.CodeBlock
	globalIndex := 1

	// Parse all files and collect blocks with filename metadata
	for _, filePath := range filePaths {
		log.Debugf("Reading file: %s", filePath)
		markdown, err := os.ReadFile(filePath)
		if err != nil {
			log.Errorf("Failed to read file %s: %s", filePath, err.Error())
			return DocciResult{
				Success:  false,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("Error reading file %s: %s", filePath, err.Error()),
			}
		}

		// Parse code blocks with filename metadata
		log.Debugf("Parsing code blocks from %s", filePath)
		fileName := filepath.Base(filePath)
		blocks, err := parser.ParseCodeBlocksWithFileName(string(markdown), fileName)
		if err != nil {
			log.Errorf("Failed to parse code blocks from %s: %s", filePath, err.Error())
			return DocciResult{
				Success:  false,
				ExitCode: 1,
				Stderr:   fmt.Sprintf("Error parsing code blocks from %s: %s", filePath, err.Error()),
			}
		}

		// Reindex blocks to ensure global uniqueness
		for i := range blocks {
			blocks[i].Index = globalIndex
			globalIndex++
		}

		allBlocks = append(allBlocks, blocks...)
		log.Debugf("Found %d code blocks in %s", len(blocks), filePath)
	}

	log.Debugf("Total merged blocks: %d", len(allBlocks))

	// Build executable script with validation markers
	log.Debug("Building executable script from merged blocks")
	script, validationMap, assertFailureMap := parser.BuildExecutableScriptWithOptions(allBlocks, hideBackgroundLogs)

	// Execute the script
	log.Debug("Executing merged script")
	resp := executor.Exec(script)

	// Check assert-failure blocks
	if len(assertFailureMap) > 0 {
		log.Debug("Checking assert-failure expectations")
		// If we have assert-failure blocks, we expect the script to fail
		if resp.Error == nil {
			log.Error("Expected script to fail due to assert-failure tag, but it succeeded")
			return DocciResult{
				Success:  false,
				ExitCode: 1,
				Stdout:   resp.Stdout,
				Stderr:   "Error: Expected script to fail with non-zero exit code due to docci-assert-failure tag, but it succeeded",
			}
		}
		log.Info("✓ Code block failed as expected due to docci-assert-failure tag")
		// Script failed as expected, continue processing
	} else if resp.Error != nil {
		// No assert-failure blocks, so error is unexpected
		log.Errorf("✗ Unexpected script execution failure: %s", resp.Error.Error())
		return DocciResult{
			Success:  false,
			ExitCode: 1,
			Stdout:   resp.Stdout,
			Stderr:   fmt.Sprintf("Error executing merged code blocks: %s", resp.Error.Error()),
		}
	}

	// Parse block outputs from the stdout
	log.Debug("Parsing block outputs")
	blockOutputs := executor.ParseBlockOutputs(resp.Stdout)

	// Validate outputs if there are any validation requirements
	var validationErrors []error
	if len(validationMap) > 0 {
		log.Debugf("Validating %d output expectations", len(validationMap))
		validationErrors = executor.ValidateOutputs(blockOutputs, validationMap)
		if len(validationErrors) > 0 {
			log.Errorf("Found %d validation errors", len(validationErrors))
			errorMsg := "\n=== Validation Errors ===\n"
			for _, err := range validationErrors {
				errorMsg += fmt.Sprintf("❌ %s\n", err.Error())
			}
			return DocciResult{
				Success:          false,
				ExitCode:         1,
				Stdout:           resp.Stdout,
				Stderr:           errorMsg,
				ValidationErrors: validationErrors,
			}
		}
		log.Debug("All validations passed")
	}

	log.Debug("Merged script execution completed successfully")
	fileList := strings.Join(filePaths, ", ")
	log.Infof("Successfully executed merged files: %s", fileList)

	return DocciResult{
		Success:          true,
		ExitCode:         0,
		Stdout:           resp.Stdout,
		Stderr:           resp.Stderr,
		ValidationErrors: nil,
	}
}
