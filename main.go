package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/reecepbcups/docci/logger"
	"github.com/reecepbcups/docci/parser"
	"github.com/reecepbcups/docci/types"
	"github.com/spf13/cobra"
)

var (
	version            = "dev"
	commit             = "none"
	date               = "unknown"
	builtBy            = "unknown"
	logLevel           string
	preCommands        []string
	cleanupCommands    []string
	hideBackgroundLogs bool
	workingDir         string
	keepRunning        bool
)

var rootCmd = &cobra.Command{
	Use:   "docci",
	Short: "Execute and validate code blocks in markdown files",
	Long: `Docci is a documentation-as-code tool that executes code blocks
in markdown files and validates their outputs.

It helps ensure your documentation examples are always accurate and working.`,
}

var runCmd = &cobra.Command{
	Use:   "run <markdown-files>",
	Short: "Execute code blocks in markdown file(s)",
	Long: `Execute all code blocks marked with 'exec' in markdown file(s).
The command will run the blocks in sequence and validate any expected outputs.
Multiple files can be specified separated by commas.`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Initialize logging based on flags
		if logLevel != "" {
			logger.SetLogLevel(logLevel)
		}

		input := args[0]
		log := logger.GetLogger()

		// Parse multiple files if provided
		filePaths := parseFileList(input)

		// Check if all files exist
		for _, filePath := range filePaths {
			if _, err := os.Stat(filePath); os.IsNotExist(err) {
				return fmt.Errorf("file not found: %s", filePath)
			}
		}

		// Validate and change working directory if workingDir is specified
		if workingDir != "" {
			if _, err := os.Stat(workingDir); os.IsNotExist(err) {
				return fmt.Errorf("run directory not found: %s", workingDir)
			}
			if err := os.Chdir(workingDir); err != nil {
				return fmt.Errorf("failed to change to run directory %s: %w", workingDir, err)
			}
			log.Infof("Changed working directory to: %s", workingDir)
		}

		if len(filePaths) == 1 {
			log.Infof("Running docci on file: %s", filePaths[0])
		} else {
			log.Infof("Running docci on %d files: %s", len(filePaths), strings.Join(filePaths, ", "))
		}

		// Run pre-commands if provided
		if len(preCommands) > 0 {
			log.Debug("Running pre-commands")
			if err := runPreCommands(preCommands); err != nil {
				return fmt.Errorf("pre-command failed: %w", err)
			}
		}

		// Run the docci command with merged files or single file

		opts := types.DocciOpts{
			HideBackgroundLogs: hideBackgroundLogs,
			KeepRunning:        keepRunning,
		}

		var result DocciResult
		if len(filePaths) == 1 {
			result = RunDocciFileWithOptions(filePaths[0], opts)
		} else {
			result = RunDocciFilesWithOptions(filePaths, opts)
		}

		// Command output is already printed by executor in real-time with filtering

		// Stderr is already printed in real-time by executor
		// No need to print again

		// Print success message for validations if applicable
		if result.Success && len(result.ValidationErrors) == 0 {
			// Check if there were any validations that passed
			hasValidations := false
			if len(filePaths) == 1 {
				markdown, _ := os.ReadFile(filePaths[0])
				blocks, _ := parser.ParseCodeBlocks(string(markdown))
				for _, block := range blocks {
					if block.OutputContains != "" {
						hasValidations = true
						break
					}
				}
			} else {
				// For multiple files, check if any had validations
				for _, filePath := range filePaths {
					markdown, _ := os.ReadFile(filePath)
					blocks, _ := parser.ParseCodeBlocks(string(markdown))
					for _, block := range blocks {
						if block.OutputContains != "" {
							hasValidations = true
							break
						}
					}
					if hasValidations {
						break
					}
				}
			}
			if hasValidations {
				log.Info("All validations passed")
			}
		}

		// Run cleanup commands if provided
		if len(cleanupCommands) > 0 {
			log.Debug("Running cleanup commands")
			runCleanupCommands(cleanupCommands)
		}

		// Exit with error if command failed
		if !result.Success {
			log.Errorf("Command failed with exit code: %d", result.ExitCode)
			os.Exit(result.ExitCode)
		}

		// Print clear success message regardless of log level
		fmt.Println("\n🎉 All tests completed successfully!")
		log.Debug("Command completed successfully")

		return nil
	},
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Display version information",
	Run: func(cmd *cobra.Command, args []string) {
		// Full version info as JSON
		versionInfo := map[string]string{
			"version":  version,
			"commit":   commit,
			"built_at": date,
			"built_by": builtBy,
			"source":   "https://github.com/reecepbcups/docci",
		}

		jsonOutput, err := json.MarshalIndent(versionInfo, "", "  ")
		if err != nil {
			fmt.Printf("Error marshaling JSON: %v\n", err)
			return
		}
		fmt.Println(string(jsonOutput))
	},
}

var validateCmd = &cobra.Command{
	Use:   "validate <markdown-file>",
	Short: "Validate markdown file without executing",
	Long:  `Parse and validate the structure of code blocks in a markdown file without executing them.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Initialize logging based on flags
		if logLevel != "" {
			logger.SetLogLevel(logLevel)
		}

		filePath := args[0]
		log := logger.GetLogger()

		// Check if file exists
		if _, err := os.Stat(filePath); os.IsNotExist(err) {
			return fmt.Errorf("file not found: %s", filePath)
		}

		log.Infof("Validating file: %s", filePath)

		// Read the file
		markdown, err := os.ReadFile(filePath)
		if err != nil {
			return fmt.Errorf("error reading file: %w", err)
		}

		// Parse code blocks
		blocks, err := parser.ParseCodeBlocks(string(markdown))
		if err != nil {
			return fmt.Errorf("error parsing code blocks: %w", err)
		}

		log.Infof("Successfully parsed %d code blocks", len(blocks))

		// Show block details at debug level
		for i, block := range blocks {
			log.Debugf("Block %d:", i+1)
			log.Debugf("  Language: %s", block.Language)
			log.Debugf("  Background: %v", block.Background)
			if block.OutputContains != "" {
				log.Debugf("  Expected output: %s", block.OutputContains)
			}
		}

		return nil
	},
}

var tagsCmd = &cobra.Command{
	Use:   "tags",
	Short: "Display all available tags and their aliases",
	Long:  `Show a comprehensive list of all docci tags, their aliases, descriptions, and usage examples.`,
	Run: func(cmd *cobra.Command, args []string) {
		tags := parser.GetAllTagsInfo()

		fmt.Println("Available Docci Tags")
		fmt.Println("====================")
		fmt.Println()

		for _, tag := range tags {
			fmt.Printf("Tag: %s\n", tag.Name)
			if len(tag.Aliases) > 0 {
				fmt.Printf("Aliases: %s\n", strings.Join(tag.Aliases, ", "))
			}
			fmt.Printf("Description: %s\n", tag.Description)
			fmt.Printf("Example: %s\n", tag.Example)
			fmt.Println()
		}

		fmt.Println("Tag Compatibility Notes:")
		fmt.Println("- Cannot use 'docci-output-contains' with 'docci-background'")
		fmt.Println("- Cannot use 'docci-assert-failure' with 'docci-background'")
		fmt.Println("- Cannot use 'docci-assert-failure' with 'docci-output-contains'")
		fmt.Println("- Cannot use 'docci-wait-for-endpoint' with 'docci-background'")
		fmt.Println("- Cannot use 'docci-retry' with 'docci-background'")
	},
}

func init() {
	// Add persistent flags
	rootCmd.PersistentFlags().StringVar(&logLevel, "log-level", "", "set log level (debug, info, warn, error, fatal, panic, off)")

	// Add commands
	rootCmd.AddCommand(runCmd)
	rootCmd.AddCommand(validateCmd)
	rootCmd.AddCommand(versionCmd)
	rootCmd.AddCommand(tagsCmd)

	// Add flags to run command
	runCmd.Flags().StringSliceVar(&preCommands, "pre-commands", []string{}, "commands to run before execution starts (useful for environment setup)")
	runCmd.Flags().StringSliceVar(&cleanupCommands, "cleanup-commands", []string{}, "commands to run after execution completes")
	runCmd.Flags().BoolVar(&hideBackgroundLogs, "hide-background-logs", false, "hide background process logs from output")
	runCmd.Flags().StringVar(&workingDir, "working-dir", "", "change working directory before running commands")
	runCmd.Flags().BoolVar(&keepRunning, "keep-running", false, "keep containers running after execution with infinite sleep")
}

func runPreCommands(commands []string) error {
	log := logger.GetLogger()
	log.Info("Running pre-commands")
	for _, command := range commands {
		log.Infof("Running: %s", command)

		// Create command
		cmd := exec.Command("bash", "-c", command)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		// Run the command
		if err := cmd.Run(); err != nil {
			log.Errorf("Error running pre-command '%s': %v", command, err)
			return fmt.Errorf("pre-command '%s' failed: %w", command, err)
		}
	}
	log.Info("Pre-commands completed successfully")
	return nil
}

func runCleanupCommands(commands []string) {
	log := logger.GetLogger()
	log.Debug("Running cleanup commands")
	for _, command := range commands {
		log.Infof("Running: %s", command)

		// Create command
		cmd := exec.Command("bash", "-c", command)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		// Run the command
		if err := cmd.Run(); err != nil {
			log.Errorf("Error running cleanup command '%s': %v", command, err)
			// Continue with other cleanup commands even if one fails
		}
	}
	log.Info("Cleanup complete")
}

// parseFileList parses comma separated file paths
func parseFileList(input string) []string {
	// Split by comma
	if !strings.Contains(input, ",") {
		// Single file
		return []string{strings.TrimSpace(input)}
	}

	files := strings.Split(input, ",")
	var result []string
	for _, file := range files {
		trimmed := strings.TrimSpace(file)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, "\nRuntime errors that occurred:", err)
		os.Exit(1)
	}
}
