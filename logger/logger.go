package logger

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
)

var Logger *slog.Logger

// ANSI color codes
const (
	colorReset  = "\033[0m"
	colorRed    = "\033[31m"
	colorYellow = "\033[33m"
	colorBlue   = "\033[34m"
	colorCyan   = "\033[36m"
)

type ColorHandler struct {
	out   io.Writer
	level slog.Leveler
}

func (h *ColorHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level.Level()
}

func (h *ColorHandler) Handle(_ context.Context, r slog.Record) error {
	timeStr := r.Time.Format("15:04:05")

	var levelColor, levelStr string
	switch r.Level {
	case slog.LevelDebug:
		levelColor = colorCyan
		levelStr = "DEBUG"
	case slog.LevelInfo:
		levelColor = colorBlue
		levelStr = "INFO"
	case slog.LevelWarn:
		levelColor = colorYellow
		levelStr = "WARN"
	case slog.LevelError:
		levelColor = colorRed
		levelStr = "ERROR"
	default:
		levelColor = colorReset
		levelStr = r.Level.String()
	}

	// Build attrs string
	var attrs string
	r.Attrs(func(a slog.Attr) bool {
		attrs += fmt.Sprintf(" %s=%v", a.Key, a.Value)
		return true
	})

	fmt.Fprintf(h.out, "%s%s%s(%s) %s%s\n",
		levelColor, levelStr, colorReset, timeStr, r.Message, attrs)
	return nil
}

func (h *ColorHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return h
}

func (h *ColorHandler) WithGroup(name string) slog.Handler {
	return h
}

func newColorHandler(out io.Writer, level slog.Leveler) *ColorHandler {
	return &ColorHandler{out: out, level: level}
}

func init() {
	Logger = slog.New(newColorHandler(os.Stderr, slog.LevelInfo))
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
	Logger = slog.New(newColorHandler(os.Stderr, lvl))
}

// GetLogger returns the configured logger instance
func GetLogger() *slog.Logger {
	return Logger
}

// IsDebugEnabled returns true if debug level logging is enabled
func IsDebugEnabled() bool {
	return Logger.Enabled(context.Background(), slog.LevelDebug)
}
