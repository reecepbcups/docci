# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Docci is a documentation-as-code tool that executes code blocks in markdown files and validates their outputs. It helps ensure documentation examples are always accurate and working.

## Architecture

The codebase is structured as follows:

- **`main.go`** - CLI interface using Cobra, handles command routing and working directory management
- **`docci.go`** - Core execution logic, orchestrates the full workflow (parse → build → execute → validate)
- **`parser/`** - Markdown parsing and code block extraction with tag processing
- **`executor/`** - Bash script execution with real-time output streaming and validation
- **`logger/`** - Centralized logging using logrus

## Build System and Dependencies

Uses Task runner (Taskfile.yml) instead of traditional Makefile:
- **Build**: `task build` → creates `out/docci` binary
- **Test**: `task test` → runs unit tests
- **Install**: `task install` → copies to `$GOPATH/bin`

Key dependencies:
- **Cobra** for CLI framework
- **Logrus** for structured logging
- **Standard library** for most functionality (minimal external deps)

## Development Workflow

### Testing Strategy
- **Unit tests**: `docci_test.go` with parallel execution
- **Integration tests**: Example markdown files in `examples/` directory
- **Test expectations**: Configured in `TestExpectations` map for files that should fail
- **Multi-file testing**: Tests file merging and environment persistence

### Example-based Testing
Tests use actual markdown files with docci tags:
- Success cases: Files that should execute successfully
- Failure cases: Defined in `TestExpectations` with expected stderr patterns
- Server endpoint tests: Special handling in `examples/server_endpoint/`

### Key Design Patterns

1. **Result Aggregation**: `DocciResult` struct contains success status, exit codes, and output
2. **Tag-based Execution**: Code blocks use docci tags for advanced behavior:
   - `docci-exec` - Execute the block
   - `docci-background` - Run in background
   - `docci-output-contains` - Validate output
   - `docci-assert-failure` - Expect failure
   - `docci-retry` - Retry on failure
   - `docci-delay` - Wait before execution
   - `docci-wait-for-endpoint` - Wait for service availability

3. **Multi-file Processing**: Blocks from multiple files are merged with global indexing
4. **Real-time Streaming**: Executor streams output in real-time while capturing for validation
5. **Conditional Execution**: OS-specific blocks and environment-based logic

## Error Handling

- **Pre-validation**: Files and working directories are validated before execution
- **Graceful failures**: Detailed error messages with context
- **Assert-failure handling**: Expected failures are treated as success
- **Validation errors**: Output mismatches are clearly reported

## Working Directory Feature

The `--working-directory` flag (alias `--working-dir`) allows changing the working directory before execution:
- Validates directory existence before execution
- Changes directory using `os.Chdir()`
- Logs directory changes for debugging

## Performance Considerations

- **Parallel testing**: Tests run concurrently using goroutines
- **Streaming output**: Real-time output prevents memory buildup
- **Efficient parsing**: Single-pass markdown parsing with regex
- **Background process management**: Proper cleanup of background processes

## Code Quality Standards

- **Error wrapping**: Uses `fmt.Errorf` with `%w` for error chains
- **Logging levels**: Debug, Info, Error levels with structured logging
- **Test isolation**: Each test runs in isolation with proper cleanup
- **Consistent naming**: Variables renamed from `runDir` to `workingDir` for clarity

## Future Considerations

- The codebase is designed for extensibility with new docci tags
- Parser and executor are decoupled for independent enhancement
- CLI flags can be easily extended through Cobra
- Multi-file processing supports complex documentation structures