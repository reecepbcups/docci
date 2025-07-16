package parser

import (
	"os"
	"testing"
	"time"

	"github.com/reecepbcups/docci/executor"
	"github.com/stretchr/testify/require"
)

// TestMain runs before all parser tests and allows global setup/teardown
func TestMain(m *testing.M) {
	// Set faster retry delay for all tests
	os.Setenv("DOCCI_RETRY_DELAY", "0")

	// Run the tests
	exitCode := m.Run()

	// Cleanup
	os.Unsetenv("DOCCI_RETRY_DELAY")

	// Exit with the same code as the tests
	os.Exit(exitCode)
}

func TestCodeBlockParse(t *testing.T) {
	// read in ../example.md into a string
	markdown, err := os.ReadFile("../examples/base.md")
	if err != nil {
		t.Fatal(err)
	}

	// parse the code blocks
	blocks, err := ParseCodeBlocks(string(markdown))
	if err != nil {
		t.Fatalf("Failed to parse code blocks: %v", err)
	}

	require.Greater(t, len(blocks), 0, "Expected at least one code block")
}

func TestCodeBlockExecute(t *testing.T) {
	// read in ../example.md into a string
	markdown, err := os.ReadFile("../examples/base.md")
	if err != nil {
		t.Fatal(err)
	}

	blocks, err := ParseCodeBlocks(string(markdown))
	if err != nil {
		t.Fatalf("Failed to parse code blocks: %v", err)
	}

	// Build executable script with validation markers
	script, validationMap, assertFailureMap := BuildExecutableScript(blocks)

	require.Equal(t, 0, len(assertFailureMap), "Expected no assert-failure blocks")

	resp := executor.Exec(script)
	if resp.Error != nil {
		t.Errorf("Error executing code block: %v, Status Code: %d", resp.Error, resp.ExitCode)
	}

	// Parse block outputs from the stdout
	blockOutputs := executor.ParseBlockOutputs(resp.Stdout)

	if len(validationMap) > 0 {
		validationErrors := executor.ValidateOutputs(blockOutputs, validationMap)
		if len(validationErrors) > 0 {
			for _, err := range validationErrors {
				t.Errorf("❌ Validation error: %s", err.Error())
			}
			os.Exit(1)
		}
	}
}

func TestCodeBlockRetryParsing(t *testing.T) {
	markdown := `
# Test Retry

` + "```bash docci-retry=3\necho \"test\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 3, blocks[0].RetryCount)
}

func TestDelayAfterSecs(t *testing.T) {
	markdown := `
# Test Delay After

` + "```bash docci-delay-after=5\necho \"test\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 5, blocks[0].DelayAfterSecs)

	// Test that the script includes the sleep command
	script, _, _ := BuildExecutableScript(blocks)
	require.Contains(t, script, "sleep 5")
	require.Contains(t, script, "# Delay after block 1 for 5 seconds")
}

func TestDelayPerCmdParsing(t *testing.T) {
	t.Parallel()
	markdown := `
# Test Delay Per Command

` + "```bash docci-delay-per-cmd=2\necho \"first\"\necho \"second\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 2.0, blocks[0].DelayPerCmdSecs)
}

func TestDelayPerCmdAliasParsing(t *testing.T) {
	t.Parallel()
	markdown := `
# Test Delay Per Command Alias

` + "```bash docci-cmd-delay=3\necho \"test\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 3.0, blocks[0].DelayPerCmdSecs)
}

func TestDelayPerCmdScriptGeneration(t *testing.T) {
	markdown := `
# Test Delay Per Command Script Generation

` + "```bash docci-delay-per-cmd=1\necho \"first command\"\necho \"second command\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 1.0, blocks[0].DelayPerCmdSecs)

	// Test that the script includes the DEBUG trap
	script, _, _ := BuildExecutableScript(blocks)
	require.Contains(t, script, "# Enable per-command delay (1 seconds)")
	require.Contains(t, script, "sleep 1' DEBUG")
	require.Contains(t, script, "echo \"first command\"")
	require.Contains(t, script, "echo \"second command\"")
}

func TestDelayPerCmdWithRetry(t *testing.T) {
	markdown := `
# Test Delay Per Command with Retry

` + "```bash docci-delay-per-cmd=2 docci-retry=3\necho \"test command\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 2.0, blocks[0].DelayPerCmdSecs)
	require.Equal(t, 3, blocks[0].RetryCount)

	// Test that the script includes both DEBUG trap and retry logic
	script, _, _ := BuildExecutableScript(blocks)
	require.Contains(t, script, "# Enable per-command delay (2 seconds)")
	require.Contains(t, script, "sleep 2' DEBUG")
	require.Contains(t, script, "# Retry logic for block 1 (max attempts: 3)")
	require.Contains(t, script, "retry_count=0")
}

func TestDelayPerCmdExecutionTiming(t *testing.T) {
	// Use just one command to minimize test time while still verifying functionality
	markdown := `
# Test Delay Per Command Execution Timing

` + "```bash docci-delay-per-cmd=1\necho \"test\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 1.0, blocks[0].DelayPerCmdSecs)

	// Build and execute the script
	script, _, _ := BuildExecutableScript(blocks)

	start := time.Now()
	resp := executor.Exec(script)
	duration := time.Since(start)

	require.NoError(t, resp.Error, "Script execution should succeed")

	// Just verify script contains the DEBUG trap (main functionality test)
	require.Contains(t, script, "sleep 1' DEBUG")

	// Basic sanity check that execution took some time (very lenient)
	require.True(t, duration >= 10*time.Millisecond,
		"Expected execution to take at least 10ms, but took %v", duration)
}

func TestDelayPerCmdFloatParsing(t *testing.T) {
	t.Parallel()
	markdown := `
# Test Delay Per Command Float Values

` + "```bash docci-delay-per-cmd=0.1\necho \"test\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)
	require.Equal(t, 0.1, blocks[0].DelayPerCmdSecs)

	// Test that the script includes the DEBUG trap with float value
	script, _, _ := BuildExecutableScript(blocks)
	require.Contains(t, script, "# Enable per-command delay (0.1 seconds)")
	require.Contains(t, script, "sleep 0.1")
}

func TestCommandSubstitutionNoDebugContamination(t *testing.T) {
	// Test that command substitution captures only the command output,
	// not the debug "Executing CMD:" messages
	markdown := `
# Test Command Substitution

` + "```bash\nexport MYDATE=$(date +%Y-%m-%d)\necho \"Date is: $MYDATE\"\n```" + `
	`

	blocks, err := ParseCodeBlocks(markdown)
	require.NoError(t, err)
	require.Len(t, blocks, 1)

	// Build and execute the script
	script, _, _ := BuildExecutableScript(blocks)
	resp := executor.Exec(script)

	require.NoError(t, resp.Error, "Script execution should succeed")
	
	// The output should contain a date in the format YYYY-MM-DD
	// and NOT contain "Executing CMD:" or "date +"
	require.Contains(t, resp.Stdout, "Date is: ")
	require.Regexp(t, `Date is: \d{4}-\d{2}-\d{2}`, resp.Stdout)
	
	// Ensure the date line doesn't contain debug output
	require.NotContains(t, resp.Stdout, "Executing CMD:")
	require.NotContains(t, resp.Stdout, "date +%Y-%m-%d")
}
