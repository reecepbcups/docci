package parser

import (
	"fmt"
	"os/exec"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"github.com/reecepbcups/docci/logger"
)

type MetaTag struct {
	Language string
	Ignore   bool

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
	ReplaceText     string

	// File operation tags
	File        string // docci-file: The file name to operate on
	ResetFile   bool   // docci-reset-file: Reset the file to its original content
	LineInsert  int    // docci-line-insert: Insert content at line N (1-based)
	LineReplace string // docci-line-replace: Replace content at line N or N-M (e.g., "3" or "7-9")
}

var tags string

const (
	TagIgnore          = "docci-ignore"
	TagOutputContains  = "docci-output-contains"
	TagBackground      = "docci-background"
	TagBackgroundKill  = "docci-background-kill"
	TagAssertFailure   = "docci-assert-failure"
	TagOS              = "docci-os"
	TagWaitForEndpoint = "docci-wait-for-endpoint"
	TagRetry           = "docci-retry"
	TagDelayBefore     = "docci-delay-before"
	TagDelayAfter      = "docci-delay-after"
	TagDelayPerCmd     = "docci-delay-per-cmd"
	TagIfFileNotExists = "docci-if-file-not-exists"
	TagIfNotInstalled  = "docci-if-not-installed"
	TagReplaceText     = "docci-replace-text"
	TagFile            = "docci-file"
	TagResetFile       = "docci-reset-file"
	TagLineInsert      = "docci-line-insert"
	TagLineReplace     = "docci-line-replace"
)

// TagInfo holds information about a tag and its aliases
type TagInfo struct {
	Name        string
	Aliases     []string
	Description string
	Example     string
}

// tagDefinitions is the single source of truth for all tag information
var tagDefinitions = []TagInfo{
	{
		Name:        TagIgnore,
		Aliases:     []string{"docci-exclude"},
		Description: "Skip execution of this code block",
		Example:     "```bash docci-ignore",
	},
	{
		Name:        TagOutputContains,
		Aliases:     []string{"docci-contains", "docci-contains-output"},
		Description: "Validate that the output contains specific text",
		Example:     "```bash docci-output-contains=\"Expected output\"",
	},
	{
		Name:        TagBackground,
		Aliases:     []string{"docci-bg"},
		Description: "Run the code block in the background",
		Example:     "```bash docci-background",
	},
	{
		Name:        TagBackgroundKill,
		Aliases:     []string{"docci-bg-kill"},
		Description: "Kill a previously started background process by index (1-based)",
		Example:     "```bash docci-background-kill=\"1\"",
	},
	{
		Name:        TagAssertFailure,
		Aliases:     []string{"docci-fail", "docci-should-fail", "docci-expect-failure"},
		Description: "Expect the code block to fail (non-zero exit code)",
		Example:     "```bash docci-assert-failure",
	},
	{
		Name:        TagOS,
		Aliases:     []string{"docci-machine"},
		Description: "Only run on specific operating systems (linux, macos, windows)",
		Example:     "```bash docci-os=\"linux\"",
	},
	{
		Name:        TagWaitForEndpoint,
		Aliases:     []string{"docci-wait"},
		Description: "Wait for HTTP endpoint before executing",
		Example:     "```bash docci-wait-for-endpoint=\"http://localhost:8080/health|30\"",
	},
	{
		Name:        TagRetry,
		Aliases:     []string{"docci-repeat"},
		Description: "Retry the code block on failure",
		Example:     "```bash docci-retry=\"3\"",
	},
	{
		Name:        TagDelayBefore,
		Aliases:     []string{"docci-before-delay"},
		Description: "Add delay before block execution (supports decimal seconds)",
		Example:     "```bash docci-delay-before=\"2.0\"",
	},
	{
		Name:        TagDelayAfter,
		Aliases:     []string{"docci-after-delay"},
		Description: "Add delay after block execution (supports decimal seconds)",
		Example:     "```bash docci-delay-after=\"1.5\"",
	},
	{
		Name:        TagDelayPerCmd,
		Aliases:     []string{"docci-cmd-delay"},
		Description: "Add delay between each command in the block",
		Example:     "```bash docci-delay-per-cmd=\"0.5\"",
	},
	{
		Name:        TagIfFileNotExists,
		Aliases:     []string{"docci-if-not-exists"},
		Description: "Only run if the specified file does not exist",
		Example:     "```bash docci-if-file-not-exists=\"/path/to/file\"",
	},
	{
		Name:        TagIfNotInstalled,
		Aliases:     []string{},
		Description: "Only run if the specified command is not installed",
		Example:     "```bash docci-if-not-installed=\"docker\"",
	},
	{
		Name:        TagReplaceText,
		Aliases:     []string{"docci-replace"},
		Description: "Replace text in the code block before execution (format: 'old;new')",
		Example:     "```bash docci-replace-text=\"bbbbbb;$SOME_ENV_VAR\"",
	},
	{
		Name:        TagFile,
		Aliases:     []string{},
		Description: "Specify the file name to operate on",
		Example:     "```html docci-file=\"example.html\"",
	},
	{
		Name:        TagResetFile,
		Aliases:     []string{},
		Description: "Reset the file to its original content (creates or overwrites)",
		Example:     "```html docci-file=\"example.html\" docci-reset-file",
	},
	{
		Name:        TagLineInsert,
		Aliases:     []string{},
		Description: "Insert content at line N (1-based)",
		Example:     "```html docci-file=\"example.html\" docci-line-insert=\"4\"",
	},
	{
		Name:        TagLineReplace,
		Aliases:     []string{},
		Description: "Replace content at line N or lines N-M (1-based)",
		Example:     "```html docci-file=\"example.html\" docci-line-replace=\"3\" or docci-line-replace=\"7-9\"",
	},
}

// tagAliasMap is built from tagDefinitions for fast lookup
var tagAliasMap map[string]string

// init builds the tagAliasMap from tagDefinitions
func init() {
	tagAliasMap = make(map[string]string)
	for _, tagInfo := range tagDefinitions {
		// Map the tag name to itself
		tagAliasMap[tagInfo.Name] = tagInfo.Name
		// Map all aliases to the tag name
		for _, alias := range tagInfo.Aliases {
			tagAliasMap[alias] = tagInfo.Name
		}
	}
}

// TagAlias returns the real tag name for a given alias.
func TagAlias(tag string) (string, error) {
	if canonicalTag, exists := tagAliasMap[tag]; exists {
		return canonicalTag, nil
	}

	return "", fmt.Errorf("unknown tag / alias: %s", tag)
}

// given a line, find any docci- tags that are present and parse them out
func ParseTags(line string) (MetaTag, error) {
	// Use regex to find all docci-* tags with optional quoted or unquoted values
	// This pattern matches:
	// - docci-tagname (no value)
	// - docci-tagname=value (unquoted value, no spaces)
	// - docci-tagname="value with spaces" (double quoted value)
	// - docci-tagname='value with spaces' (single quoted value)
	pattern := `docci-[a-zA-Z0-9-]+(?:=(?:"[^"]*"|'[^']*'|[^\s]+))?`

	re := regexp.MustCompile(pattern)
	matches := re.FindAllString(line, -1)

	logger.GetLogger().Debug("Potential tags found", "matches", matches)
	return parseTagsFromPotential(matches)
}

// parseTagsFromPotential returns an error when there is a bad tag
func parseTagsFromPotential(potential []string) (MetaTag, error) {
	// given a list of potential tags, parse them out and return a MetaTags struct
	var mt MetaTag

	for _, tag := range potential {
		// if there is a = present, we need to extract the value
		content := ""
		if strings.Contains(tag, "=") {
			logger.GetLogger().Debug("Tag with content found", "tag", tag)

			s := strings.SplitN(tag, "=", 2) // Use SplitN to only split on first =
			logger.GetLogger().Debug("Split tag into parts", "parts", s)

			tag = s[0]     // take only the tag part before the =
			content = s[1] // take the content part after the =

			// Remove quotes if present (both single and double quotes)
			if (strings.HasPrefix(content, "\"") && strings.HasSuffix(content, "\"")) ||
				(strings.HasPrefix(content, "'") && strings.HasSuffix(content, "'")) {
				content = content[1 : len(content)-1] // Remove first and last character (quotes)
			}

			tag = strings.TrimSpace(tag) // trim any spaces
		}

		// Normalize the tag using TagAlias
		normalizedTag, err := TagAlias(tag)
		if err != nil {
			return MetaTag{}, err
		}

		switch normalizedTag {
		case TagIgnore:
			mt.Ignore = true
		case TagOutputContains:
			logger.GetLogger().Debug("Output contains tag found", "tag", tag, "content", content)
			mt.OutputContains = content
		case TagBackground:
			mt.Background = true
		case TagBackgroundKill:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-background-kill requires a value (1-based index of background process to kill)")
			}
			killIndex, err := strconv.Atoi(content)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid background kill index in docci-background-kill: %s", content)
			}
			if killIndex <= 0 {
				return MetaTag{}, fmt.Errorf("background kill index must be positive (1-based) in docci-background-kill, got: %d", killIndex)
			}
			mt.BackgroundKill = killIndex
			logger.GetLogger().Debug("Background kill tag found", "index", killIndex)
		case TagAssertFailure:
			mt.AssertFailure = true
		case TagOS:
			mt.OS = content
		case TagWaitForEndpoint:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-wait-for-endpoint requires a value in format 'url|timeout_seconds'")
			}
			// Parse format: http://localhost:8080/health|30
			parts := strings.Split(content, "|")
			if len(parts) != 2 {
				return MetaTag{}, fmt.Errorf("docci-wait-for-endpoint format should be 'url|timeout_seconds', got: %s", content)
			}
			url := strings.TrimSpace(parts[0])
			timeoutStr := strings.TrimSpace(parts[1])

			timeout, err := strconv.Atoi(timeoutStr)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid timeout value in docci-wait-for-endpoint: %s", timeoutStr)
			}
			if timeout <= 0 {
				return MetaTag{}, fmt.Errorf("timeout must be positive in docci-wait-for-endpoint, got: %d", timeout)
			}

			mt.WaitForEndpoint = url
			mt.WaitTimeoutSecs = timeout
			logger.GetLogger().Debug("Wait for endpoint tag found", "url", url, "timeout_seconds", timeout)
		case TagRetry:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-retry requires a value (number of retry attempts)")
			}
			retryCount, err := strconv.Atoi(content)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid retry count in docci-retry: %s", content)
			}
			if retryCount <= 0 {
				return MetaTag{}, fmt.Errorf("retry count must be positive in docci-retry, got: %d", retryCount)
			}
			mt.RetryCount = retryCount
			logger.GetLogger().Debug("Retry tag found", "count", retryCount)
		case TagDelayBefore:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-delay-before requires a value (delay in seconds)")
			}
			delayBefore, err := strconv.ParseFloat(content, 64)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid delay seconds in docci-delay-before: %s", content)
			}
			if delayBefore <= 0 {
				return MetaTag{}, fmt.Errorf("delay seconds must be positive in docci-delay-before, got: %g", delayBefore)
			}
			mt.DelayBeforeSecs = delayBefore
			logger.GetLogger().Debug("Delay before tag found", "seconds", delayBefore)
		case TagDelayAfter:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-delay-after requires a value (delay in seconds)")
			}
			delayAfter, err := strconv.ParseFloat(content, 64)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid delay seconds in docci-delay-after: %s", content)
			}
			if delayAfter <= 0 {
				return MetaTag{}, fmt.Errorf("delay seconds must be positive in docci-delay-after, got: %g", delayAfter)
			}
			mt.DelayAfterSecs = delayAfter
			logger.GetLogger().Debug("Delay after tag found", "seconds", delayAfter)
		case TagDelayPerCmd:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-delay-per-cmd requires a value (delay in seconds)")
			}
			delayPerCmd, err := strconv.ParseFloat(content, 64)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid delay seconds in docci-delay-per-cmd: %s", content)
			}
			if delayPerCmd <= 0 {
				return MetaTag{}, fmt.Errorf("delay seconds must be positive in docci-delay-per-cmd, got: %g", delayPerCmd)
			}
			mt.DelayPerCmdSecs = delayPerCmd
			logger.GetLogger().Debug("Delay per command tag found", "seconds", delayPerCmd)
		case TagIfFileNotExists:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-if-file-not-exists requires a file path")
			}
			if strings.Contains(content, " ") {
				return MetaTag{}, fmt.Errorf("docci-if-file-not-exists does not support file paths with spaces: %s", content)
			}
			mt.IfFileNotExists = content
			logger.GetLogger().Debug("If file not exists tag found", "path", content)
		case TagIfNotInstalled:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-if-not-installed requires a command name")
			}
			if strings.Contains(content, " ") {
				return MetaTag{}, fmt.Errorf("docci-if-not-installed does not support commands with spaces: %s", content)
			}
			mt.IfNotInstalled = content
			logger.GetLogger().Debug("If not installed tag found", "command", content)
		case TagReplaceText:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-replace-text requires a value in format 'old;new'")
			}
			// Validate format: old;new
			parts := strings.SplitN(content, ";", 2)
			if len(parts) != 2 {
				return MetaTag{}, fmt.Errorf("docci-replace-text format should be 'old;new', got: %s", content)
			}
			if parts[0] == "" || parts[1] == "" {
				return MetaTag{}, fmt.Errorf("docci-replace-text both old and new text must be non-empty, got: %s", content)
			}
			mt.ReplaceText = content
			logger.GetLogger().Debug("Replace text tag found", "content", content)
		case TagFile:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-file requires a file name")
			}
			mt.File = content
			logger.GetLogger().Debug("File tag found", "name", content)
		case TagResetFile:
			mt.ResetFile = true
			logger.GetLogger().Debug("Reset file tag found")
		case TagLineInsert:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-line-insert requires a line number")
			}
			lineNum, err := strconv.Atoi(content)
			if err != nil {
				return MetaTag{}, fmt.Errorf("invalid line number in docci-line-insert: %s", content)
			}
			if lineNum <= 0 {
				return MetaTag{}, fmt.Errorf("line number must be positive (1-based) in docci-line-insert, got: %d", lineNum)
			}
			mt.LineInsert = lineNum
			logger.GetLogger().Debug("Line insert tag found", "line", lineNum)
		case TagLineReplace:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-line-replace requires a line number or range (e.g., '3' or '7-9')")
			}
			// Validate format: either a single number or N-M
			if strings.Contains(content, "-") {
				parts := strings.Split(content, "-")
				if len(parts) != 2 {
					return MetaTag{}, fmt.Errorf("invalid line range format in docci-line-replace: %s (expected 'N-M')", content)
				}
				startLine, err1 := strconv.Atoi(strings.TrimSpace(parts[0]))
				endLine, err2 := strconv.Atoi(strings.TrimSpace(parts[1]))
				if err1 != nil || err2 != nil {
					return MetaTag{}, fmt.Errorf("invalid line numbers in docci-line-replace: %s", content)
				}
				if startLine <= 0 || endLine <= 0 {
					return MetaTag{}, fmt.Errorf("line numbers must be positive (1-based) in docci-line-replace")
				}
				if startLine > endLine {
					return MetaTag{}, fmt.Errorf("start line must be <= end line in docci-line-replace: %s", content)
				}
			} else {
				// Single line number
				lineNum, err := strconv.Atoi(content)
				if err != nil {
					return MetaTag{}, fmt.Errorf("invalid line number in docci-line-replace: %s", content)
				}
				if lineNum <= 0 {
					return MetaTag{}, fmt.Errorf("line number must be positive (1-based) in docci-line-replace, got: %d", lineNum)
				}
			}
			mt.LineReplace = content
			logger.GetLogger().Debug("Line replace tag found", "range", content)
		default:
			return MetaTag{}, fmt.Errorf("unknown tag: %s", normalizedTag)
		}
	}

	return mt, nil
}

// GetCurrentOS returns the current operating system name
func GetCurrentOS() string {
	switch runtime.GOOS {
	case "linux":
		return "linux"
	case "darwin":
		return "macos"
	case "windows":
		return "windows"
	default:
		// For any other OS, return empty string to indicate unsupported
		return ""
	}
}

// ShouldRunOnCurrentOS checks if a code block should run on the current OS
func ShouldRunOnCurrentOS(blockOS string) bool {
	if blockOS == "" {
		return true // No OS restriction
	}

	currentOS := GetCurrentOS()
	// Only support the three main OS types
	switch strings.ToLower(blockOS) {
	case "mac", "osx", "macos", "darwin":
		return currentOS == "macos"
	case "win", "windows":
		return currentOS == "windows"
	case "linux":
		return currentOS == "linux"
	default:
		// Unknown OS, skip the block
		return false
	}
}

// IsCommandInstalled checks if a command is available in the system PATH
func IsCommandInstalled(command string) bool {
	_, err := exec.LookPath(command)
	return err == nil
}

// ShouldRunBasedOnCommandInstallation checks if a code block should run based on command installation status
func ShouldRunBasedOnCommandInstallation(ifNotInstalledCommand string) bool {
	if ifNotInstalledCommand == "" {
		return true // No command restriction
	}

	// Only run the block if the command is NOT installed
	isInstalled := IsCommandInstalled(ifNotInstalledCommand)
	if isInstalled {
		logger.GetLogger().Debug("Skipping code block: command already installed", "command", ifNotInstalledCommand)
	} else {
		logger.GetLogger().Debug("Including code block: command not installed", "command", ifNotInstalledCommand)
	}
	return !isInstalled
}

// GetAllTagsInfo returns information about all available tags and their aliases
func GetAllTagsInfo() []TagInfo {
	return tagDefinitions
}

// Validate checks if the tag combinations are valid
func (mt *MetaTag) Validate(lineNumber int) error {
	// Validate tag combinations
	if mt.OutputContains != "" && mt.Background {
		return fmt.Errorf("line %d: Cannot use both docci-output-contains and docci-background on the same code block", lineNumber)
	}
	if mt.AssertFailure && mt.Background {
		return fmt.Errorf("line %d: Cannot use both docci-assert-failure and docci-background on the same code block", lineNumber)
	}
	// TODO: it is possible we can allow this in the future, but need to think more about it & test (do we output contains stderr or stdout or both or?)
	if mt.AssertFailure && mt.OutputContains != "" {
		return fmt.Errorf("line %d: Cannot use both docci-assert-failure and docci-output-contains on the same code block", lineNumber)
	}
	if mt.WaitForEndpoint != "" && mt.Background {
		return fmt.Errorf("line %d: Cannot use both docci-wait-for-endpoint and docci-background on the same code block", lineNumber)
	}
	if mt.RetryCount > 0 && mt.Background {
		return fmt.Errorf("line %d: Cannot use both docci-retry and docci-background on the same code block", lineNumber)
	}

	// Validate file operations
	if mt.File != "" {
		// Can't use file operations with background blocks
		if mt.Background {
			return fmt.Errorf("line %d: Cannot use file operations with docci-background", lineNumber)
		}
		// Can't have both line-insert and line-replace
		if mt.LineInsert > 0 && mt.LineReplace != "" {
			return fmt.Errorf("line %d: Cannot use both docci-line-insert and docci-line-replace on the same code block", lineNumber)
		}
	}

	return nil
}
