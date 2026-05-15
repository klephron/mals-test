package main

import (
	"context"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"time"
)

func runnerRunServer(ctx context.Context, spec serverSpec, projectDir string, tc testCase, timeout time.Duration, includeRaw bool) (testResult, error) {
	client, err := lspStartClient(ctx, spec.Command)
	if err != nil {
		return testResult{}, err
	}
	defer client.close()

	root, err := filepath.Abs(filepath.Join(projectDir, tc.RootDir))
	if err != nil {
		return testResult{}, err
	}

	if err := runnerInitialize(ctx, client, spec, root, timeout); err != nil {
		return testResult{}, err
	}

	rec := runnerCompletion(ctx, client, spec, root, tc, timeout, includeRaw)

	_, err = client.request(ctx, "shutdown", nil, timeout)
	if err != nil {
		return rec, fmt.Errorf("shutdown: %w", err)
	}
	_ = client.notify("exit", nil)
	return rec, nil
}

func runnerInitialize(ctx context.Context, client *lspClient, spec serverSpec, root string, timeout time.Duration) error {
	initParams := map[string]any{
		"processId": os.Getpid(),
		"rootUri":   fileURI(root),
		"capabilities": map[string]any{
			"textDocument": map[string]any{
				"completion": map[string]any{
					"contextSupport": true,
					"completionItem": map[string]any{
						"snippetSupport": true,
					},
				},
			},
			"workspace": map[string]any{
				"configuration": true,
			},
		},
		"initializationOptions": spec.InitOptions,
	}
	if spec.InitOptions == nil {
		delete(initParams, "initializationOptions")
	}

	if _, err := client.request(ctx, "initialize", initParams, timeout); err != nil {
		return fmt.Errorf("initialize: %w", err)
	}
	if err := client.notify("initialized", map[string]any{}); err != nil {
		return fmt.Errorf("initialized: %w", err)
	}
	return nil
}

func runnerCompletion(ctx context.Context, client *lspClient, spec serverSpec, root string, tc testCase, timeout time.Duration, includeRaw bool) testResult {
	start := time.Now()
	res := testResult{Case: tc, Server: runnerServerLabel(spec), Method: spec.Method}
	targetAbs := filepath.Join(root, filepath.FromSlash(tc.SourceFile))
	targetURI := fileURI(targetAbs)
	pos := map[string]int{"line": tc.Cursor.Line, "character": tc.Cursor.Character}

	for _, file := range projectFiles(root, tc) {
		text, readErr := os.ReadFile(file)
		if readErr != nil {
			res.Error = readErr.Error()
			continue
		}
		rel, _ := filepath.Rel(root, file)
		err := client.notify("textDocument/didOpen", map[string]any{
			"textDocument": map[string]any{
				"uri":        fileURI(file),
				"languageId": langIDForFile(tc.Language, rel),
				"version":    1,
				"text":       string(text),
			},
		})
		if err != nil {
			res.Error = err.Error()
			break
		}
	}

	if res.Error == "" {
		params := runnerGetCompletionParams(spec, tc, targetURI, pos, targetAbs)
		raw, reqErr := client.request(ctx, spec.Method, params, timeout)
		if reqErr != nil {
			res.Error = reqErr.Error()
		} else {
			res.Completions = completionExtract(raw)
			if includeRaw {
				res.RawResult = raw
			}
		}
	}
	res.DurationMS = time.Since(start).Milliseconds()
	return res
}

func runnerGetCompletionParams(spec serverSpec, tc testCase, uri string, pos map[string]int, abs string) map[string]any {
	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     pos,
		"context":      map[string]any{"triggerKind": 1},
	}
	if spec.Method == "llm-ls/getCompletions" {
		params["uri"] = uri
		params["fileName"] = filepath.Base(abs)
		params["languageId"] = langID(tc.Language)
		params["prefix"] = tc.Prefix
		params["suffix"] = tc.Suffix
		params["maxNewTokens"] = 128
		params["max_new_tokens"] = 128
	}
	maps.Copy(params, spec.RequestOptions)
	return params
}

func runnerServerLabel(spec serverSpec) string {
	if len(spec.Command) == 0 {
		return ""
	}
	return spec.Command[0]
}
