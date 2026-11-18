package mtproto

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"amaterasu/go-engine/internal/config"

	"github.com/gotd/td/session"
	"github.com/gotd/td/telegram"
	"github.com/gotd/td/telegram/dcs"
	"github.com/gotd/td/tg"
	"github.com/gotd/td/tgerr"
	"golang.org/x/net/proxy"
)

const chunkSize = 1024 * 1024

type Credentials struct {
	AppID   int    `json:"app_id"`
	AppHash string `json:"app_hash"`
	Token   string `json:"token"`
	Proxy   Proxy  `json:"proxy"`
}

type Proxy struct {
	Scheme   string `json:"scheme"`
	Host     string `json:"host"`
	Port     int    `json:"port"`
	Username string `json:"username"`
	Password string `json:"password"`
}

func (p Proxy) resolver() (dcs.Resolver, error) {
	if p == (Proxy{}) {
		return nil, nil
	}
	if p.Scheme != "socks5" || p.Host == "" || p.Port <= 0 || p.Port > 65535 {
		return nil, errors.New("unsupported Telegram proxy")
	}
	var auth *proxy.Auth
	if p.Username != "" || p.Password != "" {
		auth = &proxy.Auth{User: p.Username, Password: p.Password}
	}
	dialer, err := proxy.SOCKS5("tcp", net.JoinHostPort(p.Host, strconv.Itoa(p.Port)), auth, proxy.Direct)
	if err != nil {
		return nil, err
	}
	return dcs.Plain(dcs.PlainOptions{Dial: dialer.(proxy.ContextDialer).DialContext}), nil
}

type worker struct {
	client     *telegram.Client
	stop       context.CancelFunc
	ready      chan struct{}
	done       chan struct{}
	slots      chan struct{}
	poolMu     sync.Mutex
	pools      map[int]telegram.CloseInvoker
	floodUntil atomic.Int64
	lastUsed   atomic.Int64
	active     atomic.Int64
}

type Engine struct {
	ctx        context.Context
	started    time.Time
	mu         sync.Mutex
	workers    map[Credentials]*worker
	registered map[string]Credentials
}

func (e *Engine) Register(cfg config.Registration) {
	next := make(map[string]Credentials, len(cfg.Tokens))
	for _, token := range cfg.Tokens {
		id, _, ok := strings.Cut(token, ":")
		if ok && id != "" {
			next[id] = Credentials{AppID: cfg.AppID, AppHash: cfg.AppHash, Token: token}
		}
	}
	e.mu.Lock()
	e.registered = next
	e.mu.Unlock()
}

func (e *Engine) ForBot(id string) (Credentials, bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	credentials, ok := e.registered[id]
	return credentials, ok
}

func New(ctx context.Context) *Engine {
	return &Engine{ctx: ctx, started: time.Now(), workers: make(map[Credentials]*worker)}
}

func (w *worker) release() {
	w.lastUsed.Store(time.Now().UnixNano())
	w.active.Add(-1)
}

func (w *worker) mediaClient(ctx context.Context, dc int) (*tg.Client, error) {
	w.poolMu.Lock()
	defer w.poolMu.Unlock()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	select {
	case <-w.done:
		return nil, errors.New("Telegram worker stopped")
	default:
	}
	invoker := w.pools[dc]
	if invoker == nil {
		var err error
		if dc == w.client.Config().ThisDC {
			invoker, err = w.client.Pool(4)
		} else {
			invoker, err = w.client.DC(ctx, dc, 4)
		}
		if err != nil {
			return nil, w.recordFlood(err)
		}
		w.pools[dc] = invoker
	}
	return tg.NewClient(invoker), nil
}

func (e *Engine) getWorker(ctx context.Context, auth Credentials) (*worker, error) {
	e.mu.Lock()
	w := e.workers[auth]
	if w == nil {
		resolver, err := auth.Proxy.resolver()
		if err != nil {
			e.mu.Unlock()
			return nil, err
		}
		if len(e.workers) >= 32 {
			var oldest *worker
			var key Credentials
			for candidate, cached := range e.workers {
				if cached.active.Load() == 0 && (oldest == nil || cached.lastUsed.Load() < oldest.lastUsed.Load()) {
					key, oldest = candidate, cached
				}
			}
			if oldest == nil {
				e.mu.Unlock()
				return nil, errors.New("account limit")
			}
			delete(e.workers, key)
			oldest.stop()
		}
		workerContext, stop := context.WithCancel(e.ctx)
		w = &worker{
			client: telegram.NewClient(auth.AppID, auth.AppHash, telegram.Options{
				NoUpdates: true, SessionStorage: &session.StorageMemory{}, Resolver: resolver,
			}),
			stop: stop, ready: make(chan struct{}), done: make(chan struct{}), slots: make(chan struct{}, 8),
			pools: make(map[int]telegram.CloseInvoker),
		}
		e.workers[auth] = w
		go func() {
			defer stop()
			_ = w.client.Run(workerContext, func(ctx context.Context) error {
				authCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
				defer cancel()
				if _, err := w.client.Auth().Bot(authCtx, auth.Token); err != nil {
					return err
				}
				close(w.ready)
				<-ctx.Done()
				return ctx.Err()
			})
			close(w.done)
			w.poolMu.Lock()
			for _, pool := range w.pools {
				_ = pool.Close()
			}
			w.poolMu.Unlock()
			e.mu.Lock()
			if e.workers[auth] == w {
				delete(e.workers, auth)
			}
			e.mu.Unlock()
		}()
	}
	w.active.Add(1)
	e.mu.Unlock()
	select {
	case <-ctx.Done():
		w.release()
		return nil, ctx.Err()
	case <-w.done:
		w.release()
		return nil, errors.New("Telegram worker stopped")
	case <-w.ready:
		return w, nil
	}
}

func (e *Engine) Health(w http.ResponseWriter, _ *http.Request) {
	ready := 0
	e.mu.Lock()
	for _, worker := range e.workers {
		select {
		case <-worker.ready:
			ready++
		default:
		}
	}
	e.mu.Unlock()
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"uptime_seconds": time.Since(e.started).Seconds(),
		"goroutines":     runtime.NumGoroutine(), "heap_bytes": memory.HeapAlloc, "ready_workers": ready,
	})
}

type MediaRange struct {
	Credentials `bson:"-"`
	DC          int    `json:"dc" bson:"dc"`
	Kind        string `json:"kind" bson:"kind"`
	ID          int64  `json:"id" bson:"id"`
	Hash        int64  `json:"access_hash" bson:"access_hash"`
	Reference   []byte `json:"file_reference" bson:"file_reference"`
	Thumb       string `json:"thumb_size" bson:"thumb_size"`
	Size        int64  `json:"size" bson:"size"`
	Start       int64  `json:"start"`
	End         int64  `json:"end"`
}

func (m MediaRange) valid() bool {
	return m.AppID > 0 && m.AppHash != "" && m.Token != "" && m.ID != 0 &&
		m.DC > 0 && m.DC < 10 && (m.Kind == "photo" || m.Kind == "document") &&
		m.Size > 0 && m.Start >= 0 && m.End >= m.Start && m.End < m.Size
}

func (m MediaRange) location() tg.InputFileLocationClass {
	if m.Kind == "photo" {
		return &tg.InputPhotoFileLocation{ID: m.ID, AccessHash: m.Hash, FileReference: m.Reference, ThumbSize: m.Thumb}
	}
	return &tg.InputDocumentFileLocation{ID: m.ID, AccessHash: m.Hash, FileReference: m.Reference, ThumbSize: m.Thumb}
}

type floodError struct {
	until  time.Time
	source int
}

func (e *floodError) Error() string { return "Telegram cooldown" }

func (e *floodError) seconds() int64 {
	return max(1, int64((time.Until(e.until)+time.Second-1)/time.Second))
}

func (w *worker) cooldown() *floodError {
	until := time.Unix(0, w.floodUntil.Load())
	if until.After(time.Now()) {
		return &floodError{until: until, source: -1}
	}
	return nil
}

func (w *worker) recordFlood(err error) error {
	wait, ok := tgerr.AsFloodWait(err)
	if !ok {
		return err
	}
	until := time.Now().Add(wait + time.Second)
	for previous := w.floodUntil.Load(); until.UnixNano() > previous; previous = w.floodUntil.Load() {
		if w.floodUntil.CompareAndSwap(previous, until.UnixNano()) {
			break
		}
	}
	return &floodError{until: time.Unix(0, w.floodUntil.Load()), source: -1}
}

func (e *Engine) Cooldown(w http.ResponseWriter, r *http.Request) {
	var auth Credentials
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 16*1024)).Decode(&auth); err != nil {
		http.Error(w, "invalid Credentials", http.StatusBadRequest)
		return
	}
	e.mu.Lock()
	worker := e.workers[auth]
	e.mu.Unlock()
	if worker != nil {
		if wait := worker.cooldown(); wait != nil {
			w.Header().Set("Retry-After", strconv.FormatInt(wait.seconds(), 10))
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}

func (w *worker) fetch(ctx context.Context, rpc *tg.Client, location tg.InputFileLocationClass, offset int64) ([]byte, error) {
	if wait := w.cooldown(); wait != nil {
		return nil, wait
	}
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	select {
	case w.slots <- struct{}{}:
		defer func() { <-w.slots }()
	case <-ctx.Done():
		return nil, ctx.Err()
	}
	if wait := w.cooldown(); wait != nil {
		return nil, wait
	}
	result, err := rpc.UploadGetFile(ctx, &tg.UploadGetFileRequest{Location: location, Offset: offset, Limit: chunkSize})
	if err != nil {
		return nil, w.recordFlood(err)
	}
	file, ok := result.(*tg.UploadFile)
	if !ok {
		return nil, errors.New("unsupported Telegram download response")
	}
	return file.Bytes, nil
}

type chunkResult struct {
	data []byte
	err  error
}

func rangeChunks(ctx context.Context, start, end int64, fetch func(context.Context, int64) ([]byte, error)) <-chan chunkResult {
	results := make(chan chunkResult, 1)
	go func() {
		defer close(results)
		ctx, cancel := context.WithCancel(ctx)
		defer cancel()
		const window = 4
		var pending [window]chan chunkResult
		last := end / chunkSize
		next := start / chunkSize
		for current := next; current <= last; current++ {
			for next <= last && next-current < window {
				ready := make(chan chunkResult, 1)
				pending[next%window] = ready
				offset := next * chunkSize
				go func() {
					data, err := fetch(ctx, offset)
					limit := min(int64(chunkSize), end-offset+1)
					if err == nil {
						if int64(len(data)) < limit {
							err = io.ErrUnexpectedEOF
						} else {
							data = data[max(0, start-offset):limit]
						}
					}
					ready <- chunkResult{data: data, err: err}
				}()
				next++
			}
			var result chunkResult
			select {
			case result = <-pending[current%window]:
			case <-ctx.Done():
				return
			}
			select {
			case results <- result:
			case <-ctx.Done():
				return
			}
			if result.err != nil {
				return
			}
		}
	}()
	return results
}

func (e *Engine) Stream(response http.ResponseWriter, request *http.Request) {
	var media MediaRange
	body := http.MaxBytesReader(response, request.Body, 16*1024)
	if err := json.NewDecoder(body).Decode(&media); err != nil || !media.valid() {
		http.Error(response, "invalid range request", http.StatusBadRequest)
		return
	}
	if err := e.ServeRange(response, request, media); err != nil {
		panic(http.ErrAbortHandler)
	}
}

func (e *Engine) ServeRange(response http.ResponseWriter, request *http.Request, media MediaRange) error {
	if !media.valid() {
		http.Error(response, "invalid media range", http.StatusBadRequest)
		return nil
	}
	ctx, cancel := context.WithCancel(request.Context())
	defer cancel()
	setup, stopSetup := context.WithTimeout(ctx, 12*time.Second)
	defer stopSetup()
	w, err := e.getWorker(setup, media.Credentials)
	if err != nil {
		http.Error(response, "Telegram worker unavailable", http.StatusServiceUnavailable)
		return nil
	}
	defer w.release()
	if wait := w.cooldown(); wait != nil {
		rangeError(response, wait)
		return nil
	}
	rpc, err := w.mediaClient(setup, media.DC)
	if err != nil {
		rangeError(response, err)
		return nil
	}
	location := media.location()
	return serveRange(response, ctx, media, func(ctx context.Context, offset int64) ([]byte, error) {
		return w.fetch(ctx, rpc, location, offset)
	})
}

func rangeError(w http.ResponseWriter, err error) {
	var wait *floodError
	if errors.As(err, &wait) {
		w.Header().Set("Retry-After", strconv.FormatInt(wait.seconds(), 10))
		http.Error(w, "Telegram cooldown", http.StatusTooManyRequests)
		return
	}
	http.Error(w, "Telegram range unavailable", http.StatusBadGateway)
}

func serveRange(response http.ResponseWriter, ctx context.Context, media MediaRange, fetch func(context.Context, int64) ([]byte, error)) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	chunks := rangeChunks(ctx, media.Start, media.End, fetch)
	first, ok := <-chunks
	if !ok || first.err != nil {
		rangeError(response, first.err)
		return nil
	}
	response.Header().Set("Accept-Ranges", "bytes")
	if response.Header().Get("Content-Type") == "" {
		response.Header().Set("Content-Type", "application/octet-stream")
	}
	response.Header().Set("Content-Length", strconv.FormatInt(media.End-media.Start+1, 10))
	response.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", media.Start, media.End, media.Size))
	response.WriteHeader(http.StatusPartialContent)
	controller := http.NewResponseController(response)
	for chunk := first; ; {
		if chunk.err != nil {
			return chunk.err
		}
		if _, err := response.Write(chunk.data); err != nil {
			return nil
		}
		if err := controller.Flush(); err != nil {
			return nil
		}
		chunk, ok = <-chunks
		if !ok {
			return nil
		}
	}
}
