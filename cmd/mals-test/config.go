package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

func configParseServers(values []string) ([]serverSpec, error) {
	var specs []serverSpec
	for _, value := range values {
		name, cmd, ok := strings.Cut(value, "=")
		if !ok || strings.TrimSpace(name) == "" || strings.TrimSpace(cmd) == "" {
			return nil, fmt.Errorf("invalid --server %q, expected name=command", value)
		}
		parts, err := configSplitCommand(cmd)
		if err != nil {
			return nil, err
		}
		specs = append(specs, serverSpec{Name: name, Command: parts})
	}
	return specs, nil
}

func configLoadNamedValues(values []string, set func(string, string)) error {
	for _, value := range values {
		name, raw, ok := strings.Cut(value, "=")
		if !ok || strings.TrimSpace(name) == "" || strings.TrimSpace(raw) == "" {
			return fmt.Errorf("invalid named value %q, expected name=value", value)
		}
		set(name, raw)
	}
	return nil
}

func configLoadNamedJSON(values []string, set func(string, map[string]any)) error {
	for _, value := range values {
		name, path, ok := strings.Cut(value, "=")
		if !ok {
			return fmt.Errorf("invalid named JSON %q, expected name=path", value)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var obj map[string]any
		if err := json.Unmarshal(data, &obj); err != nil {
			return err
		}
		set(name, obj)
	}
	return nil
}

func configSplitCommand(command string) ([]string, error) {
	var parts []string
	var b strings.Builder
	var quote rune
	escaped := false
	for _, r := range command {
		switch {
		case escaped:
			b.WriteRune(r)
			escaped = false
		case r == '\\':
			escaped = true
		case quote != 0:
			if r == quote {
				quote = 0
			} else {
				b.WriteRune(r)
			}
		case r == '\'' || r == '"':
			quote = r
		case r == ' ' || r == '\t' || r == '\n':
			if b.Len() > 0 {
				parts = append(parts, b.String())
				b.Reset()
			}
		default:
			b.WriteRune(r)
		}
	}
	if escaped {
		b.WriteRune('\\')
	}
	if quote != 0 {
		return nil, errors.New("unterminated quote in command")
	}
	if b.Len() > 0 {
		parts = append(parts, b.String())
	}
	if len(parts) == 0 {
		return nil, errors.New("empty command")
	}
	return parts, nil
}

func configDefaultCompletionMethod(name string) string {
	if name == "llm-ls" || strings.Contains(name, "llm") {
		return "llm-ls/getCompletions"
	}
	return "textDocument/completion"
}
