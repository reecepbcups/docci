package main

import (
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// TestMain runs before all tests and allows global setup/teardown
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

// TestExpectation defines the expected behavior for test files
type TestExpectation struct {
	ShouldPanic      bool   // true if we expect this test to panic/exit
	ExpectedInStderr string // string that should be present in stderr (implies ShouldFail=true)
	ExpectedInStdout string // string that should be present in stdout (optional)
}

// TestExpectations defines the expected behavior for test files that should fail
// All other files are expected to succeed by default
var TestExpectations = map[string]TestExpectation{
	"background-error-test.md": {
		ExpectedInStderr: "Cannot use both docci-output-contains and docci-background",
	},
	"assert-failure-unexpected-success.md": {
		ExpectedInStderr: "Expected script to fail with non-zero exit code due to docci-assert-failure tag, but it succeeded",
	},
	"test-background-kill-invalid.md": {
		ExpectedInStderr: "references a non-existent background process. Available background process indexes: [2]",
	},
}

// ServerEndpointTestExpectations defines expectations for server_endpoint examples
var ServerEndpointTestExpectations = map[string]TestExpectation{
	"test_incompatible_tags.md": {
		ExpectedInStderr: "Cannot use both docci-wait-for-endpoint and docci-background",
	},
	"test_wait_timeout.md": {
		ExpectedInStderr: "Error executing code block",
	},
}

type TestResult struct {
	FileName string
	Result   DocciResult
	Error    error
	Panicked bool
}

// validateTestResult validates a single test result against expectations
func validateTestResult(t *testing.T, result TestResult, expectations map[string]TestExpectation) []string {
	var failures []string

	expectation, hasExpectation := expectations[result.FileName]

	// Determine if we expect this test to fail (either explicit expectation or stderr check)
	shouldFail := hasExpectation && expectation.ExpectedInStderr != ""
	shouldPanic := hasExpectation && expectation.ShouldPanic

	// Check panic expectation
	if shouldPanic && !result.Panicked {
		failures = append(failures, result.FileName+": expected to panic but didn't")
		return failures
	}
	if !shouldPanic && result.Panicked {
		failures = append(failures, result.FileName+": unexpected panic")
		return failures
	}

	// If we expected a panic and got one, that's success - skip other checks
	if shouldPanic && result.Panicked {
		t.Logf("✓ %s: correctly panicked as expected", result.FileName)
		return failures
	}

	// Check success/failure expectation
	if shouldFail && result.Result.Success {
		failures = append(failures, result.FileName+": expected to fail but succeeded")
	}
	if !shouldFail && !result.Result.Success {
		failures = append(failures, result.FileName+": expected to succeed but failed: "+result.Result.Stderr)
	}

	// Check stdout expectations (only if we have an expectation)
	if hasExpectation && expectation.ExpectedInStdout != "" {
		if !strings.Contains(result.Result.Stdout, expectation.ExpectedInStdout) {
			failures = append(failures, result.FileName+": stdout missing expected string '"+expectation.ExpectedInStdout+"'")
		}
	}

	// Check stderr expectations (only if we have an expectation)
	if hasExpectation && expectation.ExpectedInStderr != "" {
		if !strings.Contains(result.Result.Stderr, expectation.ExpectedInStderr) {
			failures = append(failures, result.FileName+": stderr missing expected string '"+expectation.ExpectedInStderr+"'")
		}
	}

	// Log success
	if result.Result.Success {
		t.Logf("✓ %s: succeeded as expected", result.FileName)
	} else {
		t.Logf("✓ %s: failed as expected", result.FileName)
	}

	return failures
}

// runTestsOnDirectory runs tests on all .md files in a directory with given expectations
func runTestsOnDirectory(t *testing.T, pattern string, expectations map[string]TestExpectation) {
	// Find all .md files in the pattern
	files, err := filepath.Glob(pattern)
	if err != nil {
		t.Fatalf("Failed to find files with pattern %s: %v", pattern, err)
	}

	if len(files) == 0 {
		t.Skipf("No files found with pattern: %s", pattern)
	}

	// Channel to collect results
	results := make(chan TestResult, len(files))
	var wg sync.WaitGroup

	// Launch a goroutine for each file
	for _, filePath := range files {
		wg.Add(1)
		go func(path string) {
			defer wg.Done()

			fileName := filepath.Base(path)
			result := TestResult{
				FileName: fileName,
			}

			// Capture panics
			defer func() {
				if r := recover(); r != nil {
					result.Panicked = true
					result.Error = nil // Panic is expected for some tests
				}
				results <- result
			}()

			t.Logf("Testing file: %s", fileName)

			// Run the docci file
			docciResult := RunDocciFile(path)
			result.Result = docciResult

		}(filePath)
	}

	// Wait for all goroutines to complete
	go func() {
		wg.Wait()
		close(results)
	}()

	// Collect and validate results
	var failures []string
	processedCount := 0

	for result := range results {
		processedCount++
		t.Logf("Processing result for %s", result.FileName)

		resultFailures := validateTestResult(t, result, expectations)
		failures = append(failures, resultFailures...)
	}

	t.Logf("Processed %d files", processedCount)

	// Report any failures
	if len(failures) > 0 {
		t.Errorf("Test failures:\n%s", strings.Join(failures, "\n"))
	}
}

func TestAllExamples(t *testing.T) {
	runTestsOnDirectory(t, "examples/*.md", TestExpectations)
}

// TestServerEndpointExamples tests all markdown files in the examples/server_endpoint directory
func TestServerEndpointExamples(t *testing.T) {
	runTestsOnDirectory(t, "examples/server_endpoint/*.md", ServerEndpointTestExpectations)
}

func TestRunDocciFileErrorHandling(t *testing.T) {
	// Test with non-existent file
	result := RunDocciFile("non-existent-file.md")
	if result.Success {
		t.Error("Expected failure for non-existent file")
	}
	if !strings.Contains(result.Stderr, "Error reading file") {
		t.Error("Expected 'Error reading file' in stderr")
	}
}

func TestDocciResultStruct(t *testing.T) {
	// Test that DocciResult struct works correctly
	result := DocciResult{
		Success:  true,
		ExitCode: 0,
		Stdout:   "test output",
		Stderr:   "test stderr",
	}

	if !result.Success {
		t.Error("Expected success to be true")
	}
	if result.ExitCode != 0 {
		t.Error("Expected exit code to be 0")
	}
	if result.Stdout != "test output" {
		t.Error("Expected stdout to match")
	}
	if result.Stderr != "test stderr" {
		t.Error("Expected stderr to match")
	}
}

// TestMultiFileExample tests the multi-1 directory example
func TestMultiFileExample(t *testing.T) {
	// Test the multi-1 directory example
	filePaths := []string{
		"examples/multi-1/1.md",
		"examples/multi-1/2.md",
	}

	// Check if files exist
	for _, filePath := range filePaths {
		if _, err := os.Stat(filePath); os.IsNotExist(err) {
			t.Skipf("Multi-file example not found: %s", filePath)
		}
	}

	// Run the multi-file test
	result := RunDocciFiles(filePaths)

	expectation, hasExpectation := TestExpectations["multi-1"]

	// Determine if we expect this test to fail (either explicit expectation or stderr check)
	shouldFail := hasExpectation && expectation.ExpectedInStderr != ""

	// Check success/failure expectation - multi-1 should succeed by default
	if shouldFail && result.Success {
		t.Errorf("multi-1: expected to fail but succeeded")
	}
	if !shouldFail && !result.Success {
		t.Errorf("multi-1: expected to succeed but failed: %s", result.Stderr)
	}

	// Check stdout expectations (only if we have an expectation)
	if hasExpectation && expectation.ExpectedInStdout != "" {
		if !strings.Contains(result.Stdout, expectation.ExpectedInStdout) {
			t.Errorf("multi-1: stdout missing expected string '%s'. Actual stdout: %s", expectation.ExpectedInStdout, result.Stdout)
		}
	}

	// Check stderr expectations (only if we have an expectation)
	if hasExpectation && expectation.ExpectedInStderr != "" {
		if !strings.Contains(result.Stderr, expectation.ExpectedInStderr) {
			t.Errorf("multi-1: stderr missing expected string '%s'", expectation.ExpectedInStderr)
		}
	}

	// Verify that abc123 appears in output (since this is the core functionality)
	if !strings.Contains(result.Stdout, "abc123") {
		t.Errorf("multi-1: expected abc123 to appear in stdout for environment persistence test")
	}
}
