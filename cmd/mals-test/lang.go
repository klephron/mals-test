package main

import (
	"path/filepath"
	"strings"
)

func langIDForFile(fallback string, path string) string {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".py":
		return "python"
	case ".java":
		return "java"
	case ".go":
		return "go"
	case ".js", ".jsx":
		return "javascript"
	case ".ts", ".tsx":
		return "typescript"
	case ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx":
		return "cpp"
	case ".rs":
		return "rust"
	case ".cs":
		return "csharp"
	default:
		return langID(fallback)
	}
}

func langID(lang string) string {
	switch lang {
	case "js":
		return "javascript"
	case "cpp":
		return "cpp"
	case "go", "java", "python", "rust", "typescript", "csharp":
		return lang
	default:
		return lang
	}
}
