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
	"strings"
	"time"
)

type repeated []string

func (r *repeated) String() string { return strings.Join(*r, ",") }
func (r *repeated) Set(v string) error {
	*r = append(*r, v)
	return nil
}

type benchmarkCase struct {
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

type resultRecord struct {
	Case        benchmarkCase `json:"case"`
	Server      string        `json:"server"`
	Method      string        `json:"method"`
	Completion  string        `json:"completion"`
	Completions []string      `json:"completions,omitempty"`
	Metrics     metrics       `json:"metrics"`
	Error       string        `json:"error,omitempty"`
	DurationMS  int64         `json:"duration_ms"`
	RawResult   any           `json:"raw_result,omitempty"`
}

type metrics struct {
	ExactMatch           float64 `json:"exact_match"`
	EditSimilarity       float64 `json:"edit_similarity"`
	IdentifierExactMatch float64 `json:"identifier_exact_match"`
	IdentifierF1         float64 `json:"identifier_f1"`
}

type serverSpec struct {
	Name           string
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
	var servers repeated
	var initOptions repeated
	var requestOptions repeated
	var methods repeated
	var outPath string
	var timeout time.Duration
	var includeRaw bool

	flag.Var(&servers, "server", "server as name=command, for example --server lsp-ai=lsp-ai")
	flag.Var(&methods, "method", "completion method as name=method, for example --method lsp-ai=textDocument/completion")
	flag.Var(&initOptions, "init-options", "server init options as name=path/to/options.json")
	flag.Var(&requestOptions, "request-options", "extra completion request fields as name=path/to/options.json")
	flag.StringVar(&outPath, "out", "", "JSONL output path, defaults to stdout")
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

	if len(servers) == 0 {
		servers = repeated{"llm-ls=llm-ls", "lsp-ai=lsp-ai"}
	}

	serverSpecs, err := configParseServers(servers)
	must(err)
	applyNamedValues(methods, serverSpecs, func(spec *serverSpec, value string) {
		spec.Method = value
	})
	must(configLoadNamedJSON(initOptions, func(name string, obj map[string]any) {
		applyToServer(serverSpecs, name, func(spec *serverSpec) { spec.InitOptions = obj })
	}))
	must(configLoadNamedJSON(requestOptions, func(name string, obj map[string]any) {
		applyToServer(serverSpecs, name, func(spec *serverSpec) { spec.RequestOptions = obj })
	}))

	writer, closeOut := outputWriter(outPath)
	if closeOut != nil {
		defer closeOut()
	}
	enc := json.NewEncoder(writer)

	for _, spec := range serverSpecs {
		if spec.Method == "" {
			spec.Method = configDefaultCompletionMethod(spec.Name)
		}
		if err := runnerRunServer(context.Background(), spec, projectDir, project, timeout, includeRaw, enc); err != nil {
			fmt.Fprintf(os.Stderr, "server %s failed: %v\n", spec.Name, err)
		}
	}
}

func parseProjectArg() string {
	args := os.Args[1:]
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		must(flag.CommandLine.Parse(args[1:]))
		return args[0]
	}
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

func applyNamedValues(values []string, specs []serverSpec, set func(*serverSpec, string)) {
	must(configLoadNamedValues(values, func(name, value string) {
		applyToServer(specs, name, func(spec *serverSpec) { set(spec, value) })
	}))
}

func applyToServer(specs []serverSpec, name string, apply func(*serverSpec)) {
	for i := range specs {
		if specs[i].Name == name {
			apply(&specs[i])
		}
	}
}
