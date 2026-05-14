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
	add := func(rel string) {
		if rel == "" {
			return
		}
		abs := filepath.Join(root, filepath.FromSlash(rel))
		cleanRoot := filepath.Clean(root) + string(os.PathSeparator)
		cleanAbs := filepath.Clean(abs)
		if cleanAbs != filepath.Clean(root) && !strings.HasPrefix(cleanAbs, cleanRoot) {
			return
		}
		if !seen[cleanAbs] {
			seen[cleanAbs] = true
			files = append(files, cleanAbs)
		}
	}
	for _, rel := range tc.Files {
		add(rel)
	}
	add(tc.SourceFile)
	if len(files) == 0 {
		_ = filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
			if err == nil && !d.IsDir() {
				files = append(files, path)
			}
			return nil
		})
	}
	sort.Strings(files)
	return files
}
