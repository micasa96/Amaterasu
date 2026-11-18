package stream206

import (
	"container/list"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"math/big"
	"mime"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"amaterasu/go-engine/internal/config"
	"amaterasu/go-engine/internal/mtproto"
	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type metadata struct {
	BotID    string             `bson:"bot_id"`
	Filename string             `bson:"filename"`
	MIME     string             `bson:"mime_type"`
	UniqueID string             `bson:"unique_id"`
	Media    mtproto.MediaRange `bson:"media"`
}

type cacheEntry struct {
	key    string
	expiry time.Time
	value  metadata
}

type Server struct {
	engine   rangeEngine
	mu       sync.Mutex
	cfg      config.Stream
	db       *mongo.Client
	fallback http.Handler
	cache    map[string]*list.Element
	order    list.List
	peers    map[string]int
	window   time.Time
}

type rangeEngine interface {
	ForBot(string) (mtproto.Credentials, bool)
	ServeRange(http.ResponseWriter, *http.Request, mtproto.MediaRange) error
}

var proxyBuffers = sync.Pool{New: func() any { buffer := make([]byte, 32*1024); return &buffer }}

type bufferPool struct{}

func (bufferPool) Get() []byte       { return *proxyBuffers.Get().(*[]byte) }
func (bufferPool) Put(buffer []byte) { proxyBuffers.Put(&buffer) }

func New(engine rangeEngine) *Server { return &Server{engine: engine} }

func (s *Server) Configure(cfg config.Stream) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if cfg == s.cfg {
		return nil
	}
	var db *mongo.Client
	if cfg.MongoURI != "" && cfg.Partition != "" {
		var err error
		db, err = mongo.Connect(options.Client().ApplyURI(cfg.MongoURI).
			SetServerSelectionTimeout(2 * time.Second).SetMaxPoolSize(8))
		if err != nil {
			return err
		}
	}
	old := s.db
	s.cfg, s.db = cfg, db
	s.fallback = nil
	if 0 < cfg.PythonPort && cfg.PythonPort <= 65535 {
		upstream := &url.URL{Scheme: "http", Host: fmt.Sprintf("127.0.0.1:%d", cfg.PythonPort)}
		proxy := httputil.NewSingleHostReverseProxy(upstream)
		proxy.BufferPool = bufferPool{}
		direct := proxy.Director
		proxy.Director = func(r *http.Request) {
			direct(r)
			r.Header.Set("X-Amaterasu-Go-Fallback", "1")
		}
		s.fallback = proxy
	}
	s.cache = make(map[string]*list.Element)
	s.order.Init()
	if old != nil {
		go func() {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			_ = old.Disconnect(ctx)
		}()
	}
	return nil
}

func (s *Server) allow(peer string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	now := time.Now()
	if now.Sub(s.window) >= time.Minute {
		s.window, s.peers = now, make(map[string]int)
	}
	if s.peers[peer] >= 240 || (s.peers[peer] == 0 && len(s.peers) >= 4096) {
		return false
	}
	s.peers[peer]++
	return true
}

func routeKey(secret, token string) (string, bool) {
	if secret == "" || len(token) > 48 {
		return "", false
	}
	var raw []byte
	if strings.HasPrefix(token, "r") {
		code := token[1:]
		n, base := new(big.Int), big.NewInt(58)
		const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
		for _, char := range code {
			digit := strings.IndexRune(alphabet, char)
			if digit < 0 {
				n = nil
				break
			}
			n.Mul(n, base).Add(n, big.NewInt(int64(digit)))
		}
		if n != nil {
			raw = append(make([]byte, len(code)-len(strings.TrimLeft(code, "1"))), n.Bytes()...)
		}
	}
	for _, candidate := range [][]byte{raw, decodeRouteBase64(token)} {
		if len(candidate) != 24 {
			continue
		}
		mac := hmac.New(sha256.New, []byte(secret))
		mac.Write(append([]byte("stream:"), candidate[:12]...))
		if hmac.Equal(candidate[12:], mac.Sum(nil)[:12]) {
			return fmt.Sprintf("%d:%d", int64(binary.BigEndian.Uint64(candidate[:8])),
				binary.BigEndian.Uint32(candidate[8:12])), true
		}
	}
	return "", false
}

func decodeRouteBase64(token string) []byte {
	decoded, _ := base64.RawURLEncoding.DecodeString(strings.TrimRight(token, "="))
	return decoded
}

func (s *Server) lookup(ctx context.Context, cfg config.Stream, db *mongo.Client, key string) (metadata, error) {
	if db == nil {
		return metadata{}, mongo.ErrNoDocuments
	}
	s.mu.Lock()
	if item := s.cache[key]; item != nil && cfg == s.cfg && db == s.db {
		entry := item.Value.(cacheEntry)
		if entry.expiry.After(time.Now()) {
			s.order.MoveToFront(item)
			s.mu.Unlock()
			return entry.value, nil
		}
		s.order.Remove(item)
		delete(s.cache, key)
	}
	s.mu.Unlock()
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	var record metadata
	err := db.Database("amaterasu").Collection("filetolink_streams."+cfg.Partition).
		FindOne(ctx, bson.M{"_id": key}).Decode(&record)
	if err != nil {
		return metadata{}, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.db == db && s.cfg == cfg {
		if item := s.cache[key]; item != nil {
			s.order.Remove(item)
		}
		s.cache[key] = s.order.PushFront(cacheEntry{key, time.Now().Add(15 * time.Minute), record})
		if s.order.Len() > 512 {
			last := s.order.Back()
			delete(s.cache, last.Value.(cacheEntry).key)
			s.order.Remove(last)
		}
	}
	return record, nil
}

func parseRange(raw string, size int64) (start, end int64, valid bool) {
	if size <= 0 {
		return 0, 0, false
	}
	if raw == "" {
		return 0, size - 1, true
	}
	value, ok := strings.CutPrefix(raw, "bytes=")
	if !ok {
		return 0, 0, false
	}
	left, right, ok := strings.Cut(value, "-")
	if !ok {
		return 0, 0, false
	}
	if left == "" {
		n, err := strconv.ParseInt(right, 10, 64)
		if err != nil || n <= 0 {
			return 0, 0, false
		}
		return max(0, size-n), size - 1, true
	}
	start, err := strconv.ParseInt(left, 10, 64)
	if err != nil || start < 0 || start >= size {
		return 0, 0, false
	}
	end = size - 1
	if right != "" {
		n, err := strconv.ParseInt(right, 10, 64)
		if err != nil || n < start {
			return 0, 0, false
		}
		end = min(end, n)
	}
	return start, end, true
}

func safePresentation(inline bool, mediaType string) (string, string) {
	if !inline {
		return "attachment", mediaType
	}
	base, _, _ := strings.Cut(mediaType, ";")
	base = strings.ToLower(strings.TrimSpace(base))
	// Match FileToLink's Python policy for user-uploaded content on the web origin.
	switch base {
	case "image/svg+xml":
		return "attachment", mediaType
	case "application/pdf", "text/plain", "text/vtt", "text/csv", "application/x-subrip", "application/ogg", "application/x-mpegurl", "application/vnd.apple.mpegurl":
		return "inline", mediaType
	case "application/json", "application/xml", "application/javascript":
		return "inline", "text/plain; charset=utf-8"
	}
	if strings.HasPrefix(base, "video/") || strings.HasPrefix(base, "audio/") || strings.HasPrefix(base, "image/") {
		return "inline", mediaType
	}
	if strings.HasPrefix(base, "text/") || strings.HasSuffix(base, "+xml") || strings.HasSuffix(base, "+json") {
		return "inline", "text/plain; charset=utf-8"
	}
	return "attachment", mediaType
}

type rangeResponse struct {
	http.ResponseWriter
	whole, fallback, pending bool
	written                  int64
}

func (w *rangeResponse) Unwrap() http.ResponseWriter { return w.ResponseWriter }
func (w *rangeResponse) WriteHeader(status int) {
	if (status == 400 || status == 429 || status == 502 || status == 503) && w.fallback {
		w.pending = true
		return
	}
	if status == 206 && w.whole {
		w.Header().Del("Content-Range")
		status = 200
	}
	w.ResponseWriter.WriteHeader(status)
}
func (w *rangeResponse) Write(p []byte) (int, error) {
	if w.pending {
		return len(p), nil
	}
	n, err := w.ResponseWriter.Write(p)
	w.written += int64(n)
	return n, err
}

type resumedRange struct {
	out                http.ResponseWriter
	headers            http.Header
	contentRange, etag string
	remaining          int64
	accepted           bool
}

func (w *resumedRange) Header() http.Header { return w.headers }
func (w *resumedRange) WriteHeader(status int) {
	w.accepted = status == http.StatusPartialContent && w.headers.Get("Content-Range") == w.contentRange &&
		w.headers.Get("Content-Length") == strconv.FormatInt(w.remaining, 10) && w.headers.Get("ETag") == w.etag
}
func (w *resumedRange) Write(p []byte) (int, error) {
	if !w.accepted || int64(len(p)) > w.remaining {
		return 0, http.ErrAbortHandler
	}
	n, err := w.out.Write(p)
	w.remaining -= int64(n)
	return n, err
}
func (w *resumedRange) FlushError() error { return http.NewResponseController(w.out).Flush() }

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	purpose, token, _ := strings.Cut(strings.TrimPrefix(r.URL.Path, "/"), "/")
	if purpose != "stream" && purpose != "dl" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Disposition")
	if r.Method == http.MethodOptions {
		w.Header().Set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Range, Content-Type, *")
		w.WriteHeader(http.StatusNoContent)
		return
	}
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD, OPTIONS")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	peer, _, _ := net.SplitHostPort(r.RemoteAddr)
	if !s.allow(peer) {
		w.Header().Set("Retry-After", "60")
		http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
		return
	}
	s.mu.Lock()
	cfg, db, fallback := s.cfg, s.db, s.fallback
	s.mu.Unlock()
	usePython := func() {
		if fallback != nil {
			for key := range w.Header() {
				w.Header().Del(key)
			}
			fallback.ServeHTTP(w, r)
			return
		}
		http.Error(w, "stream metadata unavailable", http.StatusServiceUnavailable)
	}
	if cfg.Secret == "" || strings.Contains(token, "/") {
		usePython()
		return
	}
	key, ok := routeKey(cfg.Secret, token)
	if !ok {
		http.Error(w, "invalid stream token", http.StatusForbidden)
		return
	}
	record, err := s.lookup(r.Context(), cfg, db, key)
	if err != nil || record.Media.Size <= 0 {
		usePython()
		return
	}
	auth, ok := s.engine.ForBot(record.BotID)
	if !ok {
		usePython()
		return
	}
	record.Media.Credentials = auth
	seed := record.UniqueID
	if seed == "" {
		seed = fmt.Sprintf("%s:%d", key, record.Media.Size)
	}
	digest := sha256.Sum256([]byte(seed))
	etag := `"` + hex.EncodeToString(digest[:16]) + `"`
	w.Header().Set("ETag", etag)
	raw := r.Header.Get("Range")
	if check := r.Header.Get("If-Range"); check != "" && check != w.Header().Get("ETag") {
		raw = ""
	}
	start, end, ok := parseRange(raw, record.Media.Size)
	if !ok {
		w.Header().Set("Content-Range", fmt.Sprintf("bytes */%d", record.Media.Size))
		http.Error(w, "range not satisfiable", http.StatusRequestedRangeNotSatisfiable)
		return
	}
	record.Media.Start, record.Media.End = start, end
	inline := purpose == "stream" && strings.EqualFold(strings.TrimSpace(r.URL.Query().Get("disposition")), "inline")
	disposition, contentType := safePresentation(inline, record.MIME)
	w.Header().Set("Content-Disposition", mime.FormatMediaType(disposition, map[string]string{"filename": record.Filename}))
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("X-Content-Type-Options", "nosniff")
	base, _, _ := strings.Cut(contentType, ";")
	if !strings.EqualFold(strings.TrimSpace(base), "application/pdf") {
		w.Header().Set("Content-Security-Policy", "sandbox")
	}
	w.Header().Set("Accept-Ranges", "bytes")
	if r.Method == http.MethodHead {
		w.Header().Set("Content-Length", strconv.FormatInt(end-start+1, 10))
		if raw != "" {
			w.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", start, end, record.Media.Size))
			w.WriteHeader(206)
		}
		return
	}
	response := &rangeResponse{ResponseWriter: w, whole: raw == "", fallback: fallback != nil}
	err = s.engine.ServeRange(response, r, record.Media)
	if response.pending || err != nil {
		s.mu.Lock()
		if item := s.cache[key]; item != nil && s.cfg == cfg && db == s.db {
			s.order.Remove(item)
			delete(s.cache, key)
		}
		s.mu.Unlock()
	}
	if response.pending {
		usePython()
	} else if err != nil && r.Context().Err() == nil {
		if fallback == nil {
			panic(http.ErrAbortHandler)
		}
		next := start + response.written
		resume := r.Clone(r.Context())
		resume.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", next, end))
		resume.Header.Del("If-Range")
		tail := &resumedRange{
			out: w, headers: make(http.Header), remaining: end - next + 1, etag: etag,
			contentRange: fmt.Sprintf("bytes %d-%d/%d", next, end, record.Media.Size),
		}
		fallback.ServeHTTP(tail, resume)
		if tail.remaining != 0 {
			panic(http.ErrAbortHandler)
		}
	}
}
