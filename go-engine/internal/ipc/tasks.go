package ipc

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"regexp"
	"sync"
	"time"
)

var taskIDPattern = regexp.MustCompile(`^[a-zA-Z0-9_-]{12,96}$`)

type Tasks struct {
	ctx context.Context
	mu  sync.Mutex
	all map[string]*task
}

type task struct {
	cancel context.CancelFunc
	attach chan struct{}
	once   sync.Once
	mu     sync.Mutex
	change chan struct{}
	done   chan struct{}
	frame  []byte
}

func NewTasks(ctx context.Context) *Tasks {
	return &Tasks{ctx: ctx, all: make(map[string]*task)}
}

func (s *Tasks) Submit(run http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Old app images request inline events from the newer base image.
		if r.Header.Get("Accept") == "*/*" && r.Header.Get("X-Amaterasu-Task-ID") == "" {
			run(w, r)
			return
		}
		body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 256*1024))
		if err != nil {
			http.Error(w, "invalid task request body", http.StatusBadRequest)
			return
		}
		id := r.Header.Get("X-Amaterasu-Task-ID")
		if id == "" {
			id = rand.Text()
		}
		if !taskIDPattern.MatchString(id) {
			http.Error(w, "invalid task ID", http.StatusBadRequest)
			return
		}
		s.mu.Lock()
		if s.all[id] != nil || len(s.all) >= 256 {
			s.mu.Unlock()
			http.Error(w, "task ID exists or queue full", http.StatusConflict)
			return
		}
		ctx, cancel := context.WithTimeout(s.ctx, time.Hour)
		t := &task{cancel: cancel, attach: make(chan struct{}), change: make(chan struct{}), done: make(chan struct{})}
		s.all[id] = t
		s.mu.Unlock()
		job := r.Clone(ctx)
		job.Body = io.NopCloser(bytes.NewReader(body))
		go func() {
			defer time.AfterFunc(time.Minute, func() { s.mu.Lock(); delete(s.all, id); s.mu.Unlock() })
			defer close(t.done)
			defer cancel()
			writer := &taskWriter{task: t, headers: make(http.Header)}
			defer func() {
				if recover() != nil {
					log.Print("Go transfer task panicked")
					Events(writer).Finish(nil, context.Canceled)
				}
			}()
			timer := time.NewTimer(15 * time.Second)
			defer timer.Stop()
			select {
			case <-t.attach:
				if ctx.Err() == nil {
					run(writer, job)
				}
			case <-ctx.Done():
			case <-timer.C:
			}
		}()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_ = json.NewEncoder(w).Encode(map[string]string{"id": id})
	}
}

type taskWriter struct {
	task     *task
	headers  http.Header
	rejected bool
}

func (w *taskWriter) Header() http.Header { return w.headers }
func (w *taskWriter) Flush()              {}
func (w *taskWriter) WriteHeader(status int) {
	if status >= 400 {
		w.rejected = true
		w.publish([]byte("data: {\"status\":\"rejected\"}\n\n"))
	}
}
func (w *taskWriter) Write(b []byte) (int, error) {
	if !w.rejected {
		w.publish(b)
	}
	return len(b), nil
}
func (w *taskWriter) publish(frame []byte) {
	w.task.mu.Lock()
	defer w.task.mu.Unlock()
	w.task.frame = bytes.Clone(frame)
	close(w.task.change)
	w.task.change = make(chan struct{})
}

func (s *Tasks) lookup(id string) *task {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.all[id]
}

func (s *Tasks) Events(w http.ResponseWriter, r *http.Request) {
	t := s.lookup(r.PathValue("id"))
	if t == nil {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-store")
	ctl := http.NewResponseController(w)
	if err := ctl.Flush(); err != nil {
		return
	}
	t.once.Do(func() { close(t.attach) })
	var previous <-chan struct{}
	for {
		// Sample the completion state before the frame so a terminal event is never lost.
		done := false
		select {
		case <-t.done:
			done = true
		default:
		}
		t.mu.Lock()
		frame, change := t.frame, t.change
		t.mu.Unlock()
		if change != previous && len(frame) != 0 {
			if _, err := w.Write(frame); err != nil {
				return
			}
			if err := ctl.Flush(); err != nil {
				return
			}
		}
		if done {
			return
		}
		previous = change
		select {
		case <-r.Context().Done():
			return
		case <-t.done:
		case <-change:
		}
	}
}

func (s *Tasks) Cancel(w http.ResponseWriter, r *http.Request) {
	if t := s.lookup(r.PathValue("id")); t != nil {
		t.cancel()
		select {
		case <-t.done:
		case <-r.Context().Done():
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}
