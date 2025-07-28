package parser

import (
	"fmt"
	"regexp"
	"strings"
)

// replaceTemplateVars replaces template variables with their values
func replaceTemplateVars(template string, vars map[string]string) string {
	result := template
	for key, value := range vars {
		result = strings.ReplaceAll(result, "{{"+key+"}}", value)
	}

	// Check for any remaining unreplaced variables
	remaining := findUnreplacedVars(result)
	if len(remaining) > 0 {
		panic(fmt.Sprintf("Unreplaced template variables found: %v.\nTemplate:\n%v\n", remaining, result))
	}

	return result
}

// findUnreplacedVars finds any remaining {{VARIABLE}} patterns in the text using regex
func findUnreplacedVars(text string) []string {
	var unreplaced []string
	seen := make(map[string]bool)

	// Regex to match {{VARIABLE}} patterns
	re := regexp.MustCompile(`\{\{[^}]+\}\}`)
	matches := re.FindAllString(text, -1)

	for _, match := range matches {
		if !seen[match] {
			unreplaced = append(unreplaced, match)
			seen[match] = true
		}
	}

	return unreplaced
}

// formatFileInfo returns a formatted file info string
func formatFileInfo(fileName string) string {
	if fileName != "" {
		return fmt.Sprintf(" from %s", fileName)
	}
	return ""
}

// formatDebugCleanup returns debug cleanup message if debug level is enabled
func formatDebugCleanup(debugEnabled bool) string {
	if debugEnabled {
		return "  echo 'Cleaning up background processes...'\n"
	}
	return ""
}

// formatBashFlags returns appropriate bash flags based on assert failure setting
func formatBashFlags(assertFailure bool) string {
	if assertFailure {
		return "-T" // Don't use -e for assert-failure blocks
	}
	return "-eT"
}
