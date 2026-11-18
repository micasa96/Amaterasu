package main

import (
	"amaterasu/go-engine/internal/config"
	"amaterasu/go-engine/internal/ipc"
	"amaterasu/go-engine/internal/mtproto"
	"amaterasu/go-engine/internal/stream206"
	"amaterasu/go-engine/internal/uphoster"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"
)

func main() {
	path := flag.String("sock", "/tmp/amaterasu_go.sock", "private Unix domain socket")
	streamPort := flag.Int("stream-port", 8081, "loopback streaming port, or 0 to disable")
	flag.Parse()
	listener, err := net.Listen("unix", *path)
	if err != nil {
		log.Fatal(err)
	}
	defer listener.Close()
	if err := os.Chmod(*path, 0o600); err != nil {
		log.Print(err)
		return
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	e := mtproto.New(ctx)
	stream := stream206.New(e)
	streamServer := &http.Server{Handler: stream, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16 * 1024}
	var streamMu sync.Mutex
	var streamListener net.Listener
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/health", e.Health)
	mux.HandleFunc("POST /v1/mtproto/register-tokens", func(w http.ResponseWriter, r *http.Request) {
		var cfg config.Registration
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 64*1024)).Decode(&cfg); err != nil ||
			cfg.AppID <= 0 || cfg.AppHash == "" || len(cfg.Tokens) > 64 {
			http.Error(w, "invalid registration", http.StatusBadRequest)
			return
		}
		if cfg.Stream != nil {
			streamMu.Lock()
			defer streamMu.Unlock()
			if err := stream.Configure(*cfg.Stream); err != nil {
				http.Error(w, "invalid stream configuration", http.StatusBadRequest)
				return
			}
			if *streamPort == cfg.Stream.PythonPort || *streamPort == cfg.Stream.RclonePort {
				if streamListener != nil {
					_ = streamListener.Close()
					streamListener = nil
				}
			} else if *streamPort > 0 && streamListener == nil {
				tcp, err := net.Listen("tcp", net.JoinHostPort("127.0.0.1", strconv.Itoa(*streamPort)))
				if err != nil {
					log.Print("Go standalone streaming listener unavailable")
				} else {
					streamListener = tcp
					go func() { _ = streamServer.Serve(tcp) }()
				}
			}
		}
		e.Register(cfg)
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /v1/stream", e.Stream)
	mux.HandleFunc("POST /v1/cooldown", e.Cooldown)
	tasks := ipc.NewTasks(ctx)
	mux.HandleFunc("POST /v1/tasks/hyperdl", tasks.Submit(e.Download))
	mux.HandleFunc("POST /v1/tasks/hyperul", tasks.Submit(e.Upload))
	mux.HandleFunc("POST /v1/tasks/uphoster", tasks.Submit(uphoster.Upload))
	mux.HandleFunc("GET /v1/tasks/{id}/events", tasks.Events)
	mux.HandleFunc("DELETE /v1/tasks/{id}", tasks.Cancel)
	server := http.Server{
		Handler: mux, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second,
		BaseContext: func(net.Listener) context.Context { return ctx },
	}
	go func() {
		<-ctx.Done()
		_ = server.Close()
		_ = streamServer.Close()
	}()
	if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Print(err)
	}
}
