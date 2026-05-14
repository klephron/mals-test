package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func projectLoad(projectDir string) (testCase, error) {
	data, err := os.ReadFile(filepath.Join(projectDir, "completion.json"))
	if err != nil {
		return testCase{}, err
	}
	var tc testCase
	if err := json.Unmarshal(data, &tc); err != nil {
		return testCase{}, err
	}
	if tc.RootDir == "" {
		tc.RootDir = "root"
	}
	if tc.SourceFile == "" {
		return testCase{}, errors.New("completion.json is missing source_file")
	}
	if tc.Language == "" {
		return testCase{}, errors.New("completion.json is missing language")
	}
	root := filepath.Join(projectDir, tc.RootDir)
	if _, err := os.Stat(root); err != nil {
		return testCase{}, fmt.Errorf("project root %s: %w", root, err)
	}
	target := filepath.Join(root, filepath.FromSlash(tc.SourceFile))
	if _, err := os.Stat(target); err != nil {
		return testCase{}, fmt.Errorf("source file %s: %w", target, err)
	}
	return tc, nil
}

func projectFiles(root string, tc testCase) []string {
	seen := map[string]bool{}
	var files []string

	add := func(relPath string) {
		path, ok := projectFilePath(root, relPath)
		if !ok {
			return
		}
		if !seen[path] {
			seen[path] = true
			files = append(files, path)
		}
	}

	for _, relPath := range tc.Files {
		add(relPath)
	}
	add(tc.SourceFile)

	sort.Strings(files)
	return files
}

func projectFilePath(root string, relPath string) (string, bool) {
	if relPath == "" {
		return "", false
	}
	cleanRel := filepath.Clean(filepath.FromSlash(relPath))
	if filepath.IsAbs(cleanRel) || cleanRel == "." || cleanRel == ".." || strings.HasPrefix(cleanRel, ".."+string(os.PathSeparator)) {
		return "", false
	}
	return filepath.Join(root, cleanRel), true
}
