package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type lspClient struct {
	cmd       *exec.Cmd
	stdin     io.WriteCloser
	reader    *bufio.Reader
	writeMu   sync.Mutex
	pendingMu sync.Mutex
	pending   map[string]chan lspRpcMessage
	nextID    atomic.Int64
	closed    chan struct{}
}

type lspRpcMessage struct {
	JSONRPC string          `json:"jsonrpc,omitempty"`
	ID      any             `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *lspRpcError    `json:"error,omitempty"`
}

type lspRpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func lspStartClient(ctx context.Context, command []string) (*lspClient, error) {
	if len(command) == 0 {
		return nil, errors.New("empty command")
	}
	cmd := exec.CommandContext(ctx, command[0], command[1:]...)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	c := &lspClient{
		cmd:     cmd,
		stdin:   stdin,
		reader:  bufio.NewReader(stdout),
		pending: make(map[string]chan lspRpcMessage),
		closed:  make(chan struct{}),
	}
	go c.readLoop()
	return c, nil
}

func (c *lspClient) request(ctx context.Context, method string, params any, timeout time.Duration) (any, error) {
	id := strconv.FormatInt(c.nextID.Add(1), 10)
	ch := make(chan lspRpcMessage, 1)
	c.pendingMu.Lock()
	c.pending[id] = ch
	c.pendingMu.Unlock()
	if err := c.send(lspRpcMessage{JSONRPC: "2.0", ID: id, Method: method, Params: mustRaw(params)}); err != nil {
		return nil, err
	}
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case msg := <-ch:
		if msg.Error != nil {
			return nil, fmt.Errorf("json-rpc %d: %s", msg.Error.Code, msg.Error.Message)
		}
		var result any
		if len(msg.Result) == 0 || string(msg.Result) == "null" {
			return nil, nil
		}
		if err := json.Unmarshal(msg.Result, &result); err != nil {
			return nil, err
		}
		return result, nil
	case <-timer.C:
		c.pendingMu.Lock()
		delete(c.pending, id)
		c.pendingMu.Unlock()
		return nil, fmt.Errorf("%s timed out after %s", method, timeout)
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-c.closed:
		return nil, errors.New("language server exited")
	}
}

func (c *lspClient) notify(method string, params any) error {
	return c.send(lspRpcMessage{JSONRPC: "2.0", Method: method, Params: mustRaw(params)})
}

func (c *lspClient) send(msg lspRpcMessage) error {
	body, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	_, err = fmt.Fprintf(c.stdin, "Content-Length: %d\r\n\r\n%s", len(body), body)
	return err
}

func (c *lspClient) readLoop() {
	defer close(c.closed)
	for {
		body, err := lspReadFrame(c.reader)
		if err != nil {
			return
		}
		var msg lspRpcMessage
		if err := json.Unmarshal(body, &msg); err != nil {
			continue
		}
		if msg.ID != nil && msg.Method == "" {
			id := fmt.Sprint(msg.ID)
			c.pendingMu.Lock()
			ch := c.pending[id]
			delete(c.pending, id)
			c.pendingMu.Unlock()
			if ch != nil {
				ch <- msg
			}
			continue
		}
		if msg.ID != nil && msg.Method != "" {
			result := any(nil)
			if msg.Method == "workspace/configuration" {
				result = []any{}
			}
			_ = c.send(lspRpcMessage{JSONRPC: "2.0", ID: msg.ID, Result: mustRaw(result)})
		}
	}
}

func (c *lspClient) close() {
	_ = c.stdin.Close()
	if c.cmd.Process != nil {
		_ = c.cmd.Process.Kill()
	}
	_ = c.cmd.Wait()
}

func lspReadFrame(r *bufio.Reader) ([]byte, error) {
	length := -1
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return nil, err
		}
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			break
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 && strings.EqualFold(strings.TrimSpace(parts[0]), "Content-Length") {
			n, err := strconv.Atoi(strings.TrimSpace(parts[1]))
			if err != nil {
				return nil, err
			}
			length = n
		}
	}
	if length < 0 {
		return nil, errors.New("missing Content-Length")
	}
	body := make([]byte, length)
	_, err := io.ReadFull(r, body)
	return body, err
}
