package ipc

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestTaskHasSeparateEventsAndCancellation(t *testing.T) {
	ctx, stop := context.WithCancel(context.Background())
	defer stop()
	tasks := NewTasks(ctx)
	mux := http.NewServeMux()
	cancelled := make(chan struct{})
	mux.HandleFunc("POST /v1/tasks/test", tasks.Submit(func(w http.ResponseWriter, r *http.Request) {
		events := Events(w)
		_ = events.Progress(1, 2)
		<-r.Context().Done()
		close(cancelled)
		events.Finish(nil, r.Context().Err())
	}))
	mux.HandleFunc("GET /v1/tasks/{id}/events", tasks.Events)
	mux.HandleFunc("DELETE /v1/tasks/{id}", tasks.Cancel)
	server := httptest.NewServer(mux)
	defer server.Close()
	client := &http.Client{Timeout: 3 * time.Second}
	post, _ := http.NewRequest(http.MethodPost, server.URL+"/v1/tasks/test", strings.NewReader("{}"))
	post.Header.Set("Accept", "application/json")
	created, err := client.Do(post)
	if err != nil {
		t.Fatal(err)
	}
	var identity map[string]string
	if created.StatusCode != 202 || json.NewDecoder(created.Body).Decode(&identity) != nil || identity["id"] == "" {
		created.Body.Close()
		t.Fatal("submission did not issue an ID")
	}
	created.Body.Close()
	taskURL := fmt.Sprintf("%s/v1/tasks/%s", server.URL, identity["id"])
	events, err := client.Get(taskURL + "/events")
	if err != nil {
		t.Fatal(err)
	}
	defer events.Body.Close()
	if events.StatusCode != 200 || events.Header.Get("Content-Type") != "text/event-stream" {
		t.Fatal("missing event stream")
	}
	payload := make([]byte, 5)
	if _, err := io.ReadFull(events.Body, payload); err != nil || string(payload) != "data:" {
		t.Fatalf("missing progress event: %v", err)
	}
	cancel, _ := http.NewRequest(http.MethodDelete, taskURL, nil)
	response, err := client.Do(cancel)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != 204 {
		t.Fatalf("cancel status %d", response.StatusCode)
	}
	select {
	case <-cancelled:
	case <-time.After(time.Second):
		t.Fatal("task context survived cancellation")
	}
	terminal, err := io.ReadAll(events.Body)
	if err != nil || !strings.Contains(string(terminal), `"status":"failed"`) {
		t.Fatalf("missing terminal event: %q %v", terminal, err)
	}
}
