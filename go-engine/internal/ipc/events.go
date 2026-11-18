package ipc

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

type TransferEvents struct {
	writer http.ResponseWriter
	mu     sync.Mutex
	last   time.Time
	start  time.Time
	done   bool
}

func Events(w http.ResponseWriter) *TransferEvents {
	w.Header().Set("Content-Type", "text/event-stream")
	return &TransferEvents{writer: w, start: time.Now()}
}

func (e *TransferEvents) emit(data any) error {
	payload, err := json.Marshal(data)
	if err != nil {
		return err
	}
	if _, err := fmt.Fprintf(e.writer, "data: %s\n\n", payload); err != nil {
		return err
	}
	return http.NewResponseController(e.writer).Flush()
}

func (e *TransferEvents) Progress(current, total int64) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.done {
		return context.Canceled
	}
	if time.Since(e.last) < 250*time.Millisecond {
		return nil
	}
	e.last = time.Now()
	var speed float64
	if elapsed := e.last.Sub(e.start).Seconds(); elapsed > 0 {
		speed = float64(current) / elapsed
	}
	var eta float64
	if speed > 0 && total > current {
		eta = float64(total-current) / speed
	}
	return e.emit(map[string]any{
		"status": "running", "processed_bytes": current, "total_bytes": total,
		"speed_bps": speed, "eta_seconds": eta,
	})
}

func (e *TransferEvents) Complete(data map[string]any) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.done = true
	_ = e.emit(data)
}

func (e *TransferEvents) Finish(result any, err error) {
	if err != nil {
		e.Complete(map[string]any{"status": "failed"})
		return
	}
	e.Complete(map[string]any{"status": "complete", "result": result})
}
