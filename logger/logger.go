package logger

import (
	"context"
	"io"
	"log/slog"
	"os"
)

var Logger *slog.Logger

func init() {
	Logger = slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
}

// SetLogLevel sets the logging level based on a string
func SetLogLevel(level string) {
	var lvl slog.Level
	switch level {
	case "debug":
		lvl = slog.LevelDebug
	case "info":
		lvl = slog.LevelInfo
	case "warn", "warning":
		lvl = slog.LevelWarn
	case "error", "fatal", "panic":
		lvl = slog.LevelError
	case "off", "none":
		Logger = slog.New(slog.NewTextHandler(io.Discard, nil))
		return
	default:
		lvl = slog.LevelInfo
	}
	Logger = slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: lvl}))
}

// GetLogger returns the configured logger instance
func GetLogger() *slog.Logger {
	return Logger
}

// IsDebugEnabled returns true if debug level logging is enabled
func IsDebugEnabled() bool {
	return Logger.Enabled(context.Background(), slog.LevelDebug)
}
