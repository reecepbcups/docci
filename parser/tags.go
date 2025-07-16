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
	AssertFailure   bool
	OS              string
	WaitForEndpoint string
	WaitTimeoutSecs int
	RetryCount      int
	DelayAfterSecs  float64
	DelayPerCmdSecs float64
	IfFileNotExists string
	IfNotInstalled  string
}

var tags string

const (
	TagIgnore          = "docci-ignore"
	TagOutputContains  = "docci-output-contains"
	TagBackground      = "docci-background"
	TagAssertFailure   = "docci-assert-failure"
	TagOS              = "docci-os"
	TagWaitForEndpoint = "docci-wait-for-endpoint"
	TagRetry           = "docci-retry"
	TagDelayAfter      = "docci-delay-after"
	TagDelayPerCmd     = "docci-delay-per-cmd"
	TagIfFileNotExists = "docci-if-file-not-exists"
	TagIfNotInstalled  = "docci-if-not-installed"
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

// example input:
// ```bash docci-output-contains="Persist: test"
// ```bash docci-ignore
// func ParseTags(line string) MetaTags {
// 	// given some codeblock, parse out any tags that are present to be used
// 	// ```bash docci-output-contains="Persist: test"
// 	// ```bash docci-ignore
// 	var mt MetaTags

// 	lang := strings.TrimPrefix(line, "```")
// 	lang = strings.TrimSpace(lang)

// 	mt.Language = lang
// 	mt.Ignore = strings.Contains(line, "docci-ignore")

// 	return mt
// }

// given a line, find any docci- tags that are present and parse them out
func ParseTags(line string) (MetaTag, error) {
	// Use regex to find all docci-* tags with optional quoted or unquoted values
	// This pattern matches:
	// - docci-tagname (no value)
	// - docci-tagname=value (unquoted value, no spaces)
	// - docci-tagname="value with spaces" (quoted value)
	pattern := `docci-[a-zA-Z0-9-]+(?:=(?:"[^"]*"|[^\s]+))?`

	re := regexp.MustCompile(pattern)
	matches := re.FindAllString(line, -1)

	logger.GetLogger().Debugf("Potential tags found: %+v", matches)
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
			logger.GetLogger().Debugf("Tag with content found: %s", tag)

			s := strings.SplitN(tag, "=", 2) // Use SplitN to only split on first =
			logger.GetLogger().Debugf("Split tag into parts: %+v", s)

			tag = s[0]     // take only the tag part before the =
			content = s[1] // take the content part after the =

			// Remove quotes if present
			if strings.HasPrefix(content, "\"") && strings.HasSuffix(content, "\"") {
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
			logger.GetLogger().Debugf("Output contains tag found: %s with content: %s", tag, content)
			mt.OutputContains = content
		case TagBackground:
			mt.Background = true
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
			logger.GetLogger().Debugf("Wait for endpoint tag found: %s with timeout: %d seconds", url, timeout)
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
			logger.GetLogger().Debugf("Retry tag found with count: %d", retryCount)
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
			logger.GetLogger().Debugf("Delay after tag found with seconds: %g", delayAfter)
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
			logger.GetLogger().Debugf("Delay per command tag found with seconds: %g", delayPerCmd)
		case TagIfFileNotExists:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-if-file-not-exists requires a file path")
			}
			if strings.Contains(content, " ") {
				return MetaTag{}, fmt.Errorf("docci-if-file-not-exists does not support file paths with spaces: %s", content)
			}
			mt.IfFileNotExists = content
			logger.GetLogger().Debugf("If file not exists tag found with path: %s", content)
		case TagIfNotInstalled:
			if content == "" {
				return MetaTag{}, fmt.Errorf("docci-if-not-installed requires a command name")
			}
			if strings.Contains(content, " ") {
				return MetaTag{}, fmt.Errorf("docci-if-not-installed does not support commands with spaces: %s", content)
			}
			mt.IfNotInstalled = content
			logger.GetLogger().Debugf("If not installed tag found with command: %s", content)
		default:
			return MetaTag{}, fmt.Errorf("unknown tag found: %s", tag)
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
		logger.GetLogger().Debugf("Skipping code block: command '%s' is already installed", ifNotInstalledCommand)
	} else {
		logger.GetLogger().Debugf("Including code block: command '%s' is not installed", ifNotInstalledCommand)
	}
	return !isInstalled
}

// GetAllTagsInfo returns information about all available tags and their aliases
func GetAllTagsInfo() []TagInfo {
	return tagDefinitions
}
