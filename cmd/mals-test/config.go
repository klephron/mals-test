package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/google/shlex"
)

func configParseServer(value string) (serverSpec, error) {
	if strings.TrimSpace(value) == "" {
		return serverSpec{}, fmt.Errorf("empty --server command")
	}
	parts, err := configSplitCommand(value)
	if err != nil {
		return serverSpec{}, err
	}
	name := parts[0]
	return serverSpec{Name: name, Command: parts}, nil
}

func configLoadJSONFile(path string) map[string]any {
	if path == "" {
		return nil
	}
	data, err := os.ReadFile(path)
	must(err)
	var obj map[string]any
	must(json.Unmarshal(data, &obj))
	return obj
}

func configSplitCommand(command string) ([]string, error) {
	parts, err := shlex.Split(command)
	if err != nil {
		return nil, err
	}
	if len(parts) == 0 {
		return nil, fmt.Errorf("empty command")
	}
	return parts, nil
}

func configDefaultCompletionMethod(name string) string {
	if name == "llm-ls" || strings.Contains(name, "llm") {
		return "llm-ls/getCompletions"
	}
	return "textDocument/completion"
}
