package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"time"
)

type testCase struct {
	ID          string         `json:"id"`
	Dataset     string         `json:"dataset"`
	Language    string         `json:"language"`
	RootDir     string         `json:"root_dir"`
	SourceFile  string         `json:"source_file"`
	Cursor      cursorPosition `json:"cursor"`
	Prefix      string         `json:"prefix"`
	Suffix      string         `json:"suffix,omitempty"`
	GroundTruth string         `json:"ground_truth"`
	Files       []string       `json:"files,omitempty"`
	Metadata    map[string]any `json:"metadata,omitempty"`
}

type cursorPosition struct {
	Line      int `json:"line"`
	Character int `json:"character"`
	Offset    int `json:"offset,omitempty"`
}

type testResult struct {
	Case        testCase `json:"case"`
	Server      string   `json:"server"`
	Method      string   `json:"method"`
	Completions []string `json:"completions,omitempty"`
	Error       string   `json:"error,omitempty"`
	DurationMS  int64    `json:"duration_ms"`
	RawResult   any      `json:"raw_result,omitempty"`
}

type serverSpec struct {
	Command        []string
	Method         string
	InitOptions    map[string]any
	RequestOptions map[string]any
}

func must(err error) {
	if err != nil {
		var buf bytes.Buffer
		fmt.Fprintf(&buf, "error: %v\n", err)
		_, _ = os.Stderr.Write(buf.Bytes())
		os.Exit(1)
	}
}

func mustRaw(v any) json.RawMessage {
	if v == nil {
		return json.RawMessage("null")
	}
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}

func fileURI(path string) string {
	u := url.URL{Scheme: "file", Path: filepath.ToSlash(path)}
	return u.String()
}

func main() {
	var server string
	var method string
	var initOptions string
	var requestOptions string
	var outPath string
	var timeout time.Duration
	var includeRaw bool

	flag.StringVar(&server, "server", "", "server command, for example --server lsp-ai")
	flag.StringVar(&method, "method", "", "completion method, for example --method textDocument/completion")
	flag.StringVar(&initOptions, "init-options", "", "server init options JSON path")
	flag.StringVar(&requestOptions, "request-options", "", "extra completion request fields JSON path")
	flag.StringVar(&outPath, "out", "", "output path, defaults to stdout")
	flag.DurationVar(&timeout, "timeout", 2*time.Minute, "timeout per LSP request")
	flag.BoolVar(&includeRaw, "raw", false, "include raw completion response in output")

	projectArg := parseProjectArg()
	if projectArg == "" {
		must(errors.New("usage: lspbench [flags] <project-dir-with-completion.json-and-root>"))
	}
	projectDir, err := filepath.Abs(projectArg)
	must(err)
	project, err := projectLoad(projectDir)
	must(err)

	if server == "" {
		must(errors.New("--server is required, for example --server lsp-ai"))
	}

	serverSpec, err := configParseServer(server)
	must(err)
	if method == "" {
		must(errors.New("--method is required, for example --method textDocument/completion"))
	}
	serverSpec.Method = method
	serverSpec.InitOptions = configLoadJSONFile(initOptions)
	serverSpec.RequestOptions = configLoadJSONFile(requestOptions)

	writer, closeOut := outputWriter(outPath)
	if closeOut != nil {
		defer closeOut()
	}

	record, err := runnerRunServer(context.Background(), serverSpec, projectDir, project, timeout, includeRaw)
	if err != nil {
		fmt.Fprintf(os.Stderr, "server %s failed: %v\n", runnerServerLabel(serverSpec), err)
		os.Exit(1)
	}
	enc := json.NewEncoder(writer)
	enc.SetIndent("", "  ")
	must(enc.Encode(record))
	if err != nil {
		os.Exit(1)
	}
}

func parseProjectArg() string {
	flag.Parse()
	if flag.NArg() == 1 {
		return flag.Arg(0)
	}
	return ""
}

func outputWriter(outPath string) (io.Writer, func()) {
	if outPath == "" {
		return os.Stdout, nil
	}
	must(os.MkdirAll(filepath.Dir(outPath), 0o755))
	out, err := os.Create(outPath)
	must(err)
	return out, func() { _ = out.Close() }
}
