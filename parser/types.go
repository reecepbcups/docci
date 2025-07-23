package parser

import "strings"

// codeBlockState holds the current state during parsing
// TODO: see if we can merge this with the finalized CodeBlock state somehow?
type codeBlockState struct {
	lang            string  `default:""`
	outputContains  string  `default:""`
	background      bool    `default:"false"`
	assertFailure   bool    `default:"false"`
	os              string  `default:""`
	waitForEndpoint string  `default:""`
	waitTimeoutSecs int     `default:"0"`
	retryCount      int     `default:"0"`
	delayBeforeSecs float64 `default:"0.0"`
	delayAfterSecs  float64 `default:"0.0"`
	delayPerCmdSecs float64 `default:"0.0"`
	ifFileNotExists string  `default:""`
	ifNotInstalled  string  `default:""`
	replaceText     string  `default:""`
	lineNumber      int     `default:"0"`
	content         strings.Builder
}

// newCodeBlockState creates a new codeBlockState with default values
func newCodeBlockState() *codeBlockState {
	return &codeBlockState{}
}

// reset clears the state for the next code block
func (s *codeBlockState) reset() {
	*s = *newCodeBlockState()
}

// applyTags applies parsed tags to the current state
func (s *codeBlockState) applyTags(tags MetaTag, lang string, lineNumber int) {
	s.lang = lang
	s.outputContains = tags.OutputContains
	s.background = tags.Background
	s.assertFailure = tags.AssertFailure
	s.os = tags.OS
	s.waitForEndpoint = tags.WaitForEndpoint
	s.waitTimeoutSecs = tags.WaitTimeoutSecs
	s.retryCount = tags.RetryCount
	s.delayBeforeSecs = tags.DelayBeforeSecs
	s.delayAfterSecs = tags.DelayAfterSecs
	s.delayPerCmdSecs = tags.DelayPerCmdSecs
	s.ifFileNotExists = tags.IfFileNotExists
	s.ifNotInstalled = tags.IfNotInstalled
	s.replaceText = tags.ReplaceText
	s.lineNumber = lineNumber
	s.content.Reset()
}

// toCodeBlock converts the current state to a CodeBlock
func (s *codeBlockState) toCodeBlock(index int, fileName string) CodeBlock {
	return CodeBlock{
		Index:           index,
		Language:        s.lang,
		Content:         s.content.String(),
		OutputContains:  s.outputContains,
		Background:      s.background,
		AssertFailure:   s.assertFailure,
		OS:              s.os,
		WaitForEndpoint: s.waitForEndpoint,
		WaitTimeoutSecs: s.waitTimeoutSecs,
		RetryCount:      s.retryCount,
		DelayBeforeSecs: s.delayBeforeSecs,
		DelayAfterSecs:  s.delayAfterSecs,
		DelayPerCmdSecs: s.delayPerCmdSecs,
		IfFileNotExists: s.ifFileNotExists,
		LineNumber:      s.lineNumber,
		FileName:        fileName,
		ReplaceText:     s.replaceText,
	}
}
