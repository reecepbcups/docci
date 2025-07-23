package parser

import (
	"testing"

	"github.com/stretchr/testify/require"
	// "github.com/stretchr/testify/require"
)

func TestTagsGeneric(t *testing.T) {
	mt, err := ParseTags("```bash docci-ignore")
	require.NoError(t, err)
	require.True(t, mt.Ignore)
	require.Empty(t, mt.OutputContains)

	// errors due to bad tag
	_, err = ParseTags("```bash docci-bad-tag")
	require.Error(t, err)
}

func TestContains(t *testing.T) {
	pt, err := ParseTags("```bash docci-output-contains=\"test\"")
	require.NoError(t, err)
	require.Contains(t, pt.OutputContains, "test")

	pt, err = ParseTags("```bash docci-output-contains=\"test 123\"")
	require.NoError(t, err)
	require.Contains(t, pt.OutputContains, "test 123")
}

func TestWaitForEndpoint(t *testing.T) {
	// Test valid wait-for-endpoint tag
	pt, err := ParseTags("```bash docci-wait-for-endpoint=\"http://localhost:8080/health|30\"")
	require.NoError(t, err)
	require.Equal(t, "http://localhost:8080/health", pt.WaitForEndpoint)
	require.Equal(t, 30, pt.WaitTimeoutSecs)

	// Test alias
	pt, err = ParseTags("```bash docci-wait=\"http://localhost:9000/status|15\"")
	require.NoError(t, err)
	require.Equal(t, "http://localhost:9000/status", pt.WaitForEndpoint)
	require.Equal(t, 15, pt.WaitTimeoutSecs)

	// Test invalid format - missing pipe
	_, err = ParseTags("```bash docci-wait-for-endpoint=\"http://localhost:8080/health\"")
	require.Error(t, err)
	require.Contains(t, err.Error(), "format should be")

	// Test invalid format - invalid timeout
	_, err = ParseTags("```bash docci-wait-for-endpoint=\"http://localhost:8080/health|abc\"")
	require.Error(t, err)
	require.Contains(t, err.Error(), "invalid timeout value")

	// Test invalid format - negative timeout
	_, err = ParseTags("```bash docci-wait-for-endpoint=\"http://localhost:8080/health|-5\"")
	require.Error(t, err)
	require.Contains(t, err.Error(), "timeout must be positive")

	// Test empty value
	_, err = ParseTags("```bash docci-wait-for-endpoint")
	require.Error(t, err)
	require.Contains(t, err.Error(), "requires a value")
}

func TestRetry(t *testing.T) {
	// Test valid retry tag
	pt, err := ParseTags("```bash docci-retry=3")
	require.NoError(t, err)
	require.Equal(t, 3, pt.RetryCount)

	// Test quoted value
	pt, err = ParseTags("```bash docci-retry=\"5\"")
	require.NoError(t, err)
	require.Equal(t, 5, pt.RetryCount)

	// Test alias
	pt, err = ParseTags("```bash docci-repeat=2")
	require.NoError(t, err)
	require.Equal(t, 2, pt.RetryCount)

	// Test invalid value - not a number
	_, err = ParseTags("```bash docci-retry=abc")
	require.Error(t, err)
	require.Contains(t, err.Error(), "invalid retry count")

	// Test invalid value - negative number
	_, err = ParseTags("```bash docci-retry=-1")
	require.Error(t, err)
	require.Contains(t, err.Error(), "retry count must be positive")

	// Test invalid value - zero
	_, err = ParseTags("```bash docci-retry=0")
	require.Error(t, err)
	require.Contains(t, err.Error(), "retry count must be positive")

	// Test empty value
	_, err = ParseTags("```bash docci-retry")
	require.Error(t, err)
	require.Contains(t, err.Error(), "requires a value")
}

func TestDelayPerCmd(t *testing.T) {
	// Test valid delay-per-cmd tag
	pt, err := ParseTags("```bash docci-delay-per-cmd=2")
	require.NoError(t, err)
	require.Equal(t, 2.0, pt.DelayPerCmdSecs)

	// Test quoted value
	pt, err = ParseTags("```bash docci-delay-per-cmd=\"3\"")
	require.NoError(t, err)
	require.Equal(t, 3.0, pt.DelayPerCmdSecs)

	// Test alias
	pt, err = ParseTags("```bash docci-cmd-delay=5")
	require.NoError(t, err)
	require.Equal(t, 5.0, pt.DelayPerCmdSecs)

	// Test decimal values
	pt, err = ParseTags("```bash docci-delay-per-cmd=0.1")
	require.NoError(t, err)
	require.Equal(t, 0.1, pt.DelayPerCmdSecs)

	// Test float with alias
	pt, err = ParseTags("```bash docci-cmd-delay=1.5")
	require.NoError(t, err)
	require.Equal(t, 1.5, pt.DelayPerCmdSecs)

	// Test invalid value - not a number
	_, err = ParseTags("```bash docci-delay-per-cmd=abc")
	require.Error(t, err)
	require.Contains(t, err.Error(), "invalid delay seconds")

	// Test invalid value - negative number
	_, err = ParseTags("```bash docci-delay-per-cmd=-1")
	require.Error(t, err)
	require.Contains(t, err.Error(), "delay seconds must be positive")

	// Test invalid value - zero
	_, err = ParseTags("```bash docci-delay-per-cmd=0")
	require.Error(t, err)
	require.Contains(t, err.Error(), "delay seconds must be positive")

	// Test empty value
	_, err = ParseTags("```bash docci-delay-per-cmd")
	require.Error(t, err)
	require.Contains(t, err.Error(), "requires a value")
}

func TestDelayBefore(t *testing.T) {
	// Test valid delay-before tag
	pt, err := ParseTags("```bash docci-delay-before=2")
	require.NoError(t, err)
	require.Equal(t, 2.0, pt.DelayBeforeSecs)

	// Test quoted value
	pt, err = ParseTags("```bash docci-delay-before=\"3.5\"")
	require.NoError(t, err)
	require.Equal(t, 3.5, pt.DelayBeforeSecs)

	// Test alias
	pt, err = ParseTags("```bash docci-before-delay=1.5")
	require.NoError(t, err)
	require.Equal(t, 1.5, pt.DelayBeforeSecs)

	// Test decimal values
	pt, err = ParseTags("```bash docci-delay-before=0.5")
	require.NoError(t, err)
	require.Equal(t, 0.5, pt.DelayBeforeSecs)

	// Test invalid value - not a number
	_, err = ParseTags("```bash docci-delay-before=abc")
	require.Error(t, err)
	require.Contains(t, err.Error(), "invalid delay seconds")

	// Test invalid value - negative number
	_, err = ParseTags("```bash docci-delay-before=-1")
	require.Error(t, err)
	require.Contains(t, err.Error(), "delay seconds must be positive")

	// Test invalid value - zero
	_, err = ParseTags("```bash docci-delay-before=0")
	require.Error(t, err)
	require.Contains(t, err.Error(), "delay seconds must be positive")

	// Test empty value
	_, err = ParseTags("```bash docci-delay-before")
	require.Error(t, err)
	require.Contains(t, err.Error(), "requires a value")
}
