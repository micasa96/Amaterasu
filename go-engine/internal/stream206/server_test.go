package stream206

import (
	"bytes"
	"container/list"
	"crypto/sha256"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"amaterasu/go-engine/internal/mtproto"
	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

// Produced by Python's make_route_token("fixture", "stream", -10042, 7).
const fixtureToken = "rQLbz7JHi9qWb1yRsgBaAbqEHG2HLMTFuq"

type fixtureEngine struct {
	data   []byte
	broken bool
}

func (e fixtureEngine) ForBot(id string) (mtproto.Credentials, bool) {
	return mtproto.Credentials{Token: "1:fixture"}, id == "1"
}

func (e fixtureEngine) ServeRange(w http.ResponseWriter, _ *http.Request, media mtproto.MediaRange) error {
	w.Header().Set("Content-Length", strconv.FormatInt(media.End-media.Start+1, 10))
	w.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", media.Start, media.End, media.Size))
	w.WriteHeader(http.StatusPartialContent)
	data := e.data[media.Start : media.End+1]
	if e.broken {
		_, _ = w.Write(data[:3])
		return errors.New("fixture Telegram failure")
	}
	_, err := w.Write(data)
	return err
}

func fixtureServer(engine fixtureEngine) *Server {
	s := New(engine)
	// Seed a cache hit so these HTTP tests need no external MongoDB or Telegram.
	s.cfg.Secret = "fixture"
	s.db = new(mongo.Client)
	record := metadata{BotID: "1", Filename: "video.mp4", MIME: "video/mp4", UniqueID: "unique",
		Media: mtproto.MediaRange{Size: int64(len(engine.data))}}
	s.cache = map[string]*list.Element{
		"-10042:7": s.order.PushFront(cacheEntry{"-10042:7", time.Now().Add(time.Minute), record}),
	}
	return s
}

func TestSignedHTTPRanges(t *testing.T) {
	data := bytes.Repeat([]byte("0123456789abc"), 2*1024*1024)
	s := fixtureServer(fixtureEngine{data: data})
	const size = 10485760
	for _, method := range []string{http.MethodGet, http.MethodHead} {
		r := httptest.NewRequest(method, "/stream/"+fixtureToken, nil)
		r.Header.Set("Range", "bytes=10485760-20971519")
		response := httptest.NewRecorder()
		s.ServeHTTP(response, r)
		if response.Code != 206 || response.Header().Get("Content-Length") != "10485760" ||
			response.Header().Get("Content-Range") != fmt.Sprintf("bytes 10485760-20971519/%d", len(data)) {
			t.Fatalf("unexpected %s response: %d %v", method, response.Code, response.Header())
		}
		if method == http.MethodGet && sha256.Sum256(response.Body.Bytes()) != sha256.Sum256(data[size:2*size]) {
			t.Fatal("range differs from original data")
		}
		if method == http.MethodHead && response.Body.Len() != 0 {
			t.Fatal("HEAD returned a response body")
		}
	}
	r := httptest.NewRequest(http.MethodGet, "/dl/"+fixtureToken, nil)
	r.Header.Set("Range", "bytes=999999999-")
	response := httptest.NewRecorder()
	s.ServeHTTP(response, r)
	if response.Code != 416 || response.Header().Get("Content-Range") != fmt.Sprintf("bytes */%d", len(data)) {
		t.Fatalf("invalid unsatisfiable range response: %d %v", response.Code, response.Header())
	}
	response = httptest.NewRecorder()
	s.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/stream/"+fixtureToken+"f", nil))
	if response.Code != 403 {
		t.Fatalf("tampered token returned %d", response.Code)
	}
}

func TestSignedStreamProtectsInlineContent(t *testing.T) {
	for _, test := range []struct{ mediaType, disposition, contentType, csp string }{
		{"text/html; charset=UTF-8", "inline", "text/plain; charset=utf-8", "sandbox"},
		{"image/svg+xml", "attachment", "image/svg+xml", "sandbox"},
		{"application/pdf", "inline", "application/pdf", ""},
		{"video/mp4", "inline", "video/mp4", "sandbox"},
	} {
		s := fixtureServer(fixtureEngine{data: []byte("fixture")})
		entry := s.cache["-10042:7"].Value.(cacheEntry)
		entry.value.MIME = test.mediaType
		s.cache["-10042:7"].Value = entry
		r := httptest.NewRequest(http.MethodGet, "/stream/"+fixtureToken+"?disposition=inline", nil)
		response := httptest.NewRecorder()
		s.ServeHTTP(response, r)
		h := response.Header()
		if response.Code != 200 || !strings.HasPrefix(h.Get("Content-Disposition"), test.disposition+";") ||
			h.Get("Content-Type") != test.contentType || h.Get("Content-Security-Policy") != test.csp ||
			h.Get("X-Content-Type-Options") != "nosniff" {
			t.Errorf("unexpected response for %s: %d %v", test.mediaType, response.Code, h)
		}
	}
}

func TestInterruptedStreamResumesAtNextByte(t *testing.T) {
	s := fixtureServer(fixtureEngine{data: []byte("abcdefghij"), broken: true})
	s.fallback = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Range"); got != "bytes=5-8" {
			t.Fatalf("resumed range %s", got)
		}
		w.Header().Set("Content-Range", "bytes 5-8/10")
		w.Header().Set("Content-Length", "4")
		digest := sha256.Sum256([]byte("unique"))
		w.Header().Set("ETag", fmt.Sprintf(`"%x"`, digest[:16]))
		w.WriteHeader(http.StatusPartialContent)
		_, _ = w.Write([]byte("fghi"))
	})
	r := httptest.NewRequest(http.MethodGet, "/stream/"+fixtureToken, nil)
	r.Header.Set("Range", "bytes=2-8")
	response := httptest.NewRecorder()
	s.ServeHTTP(response, r)
	if response.Code != 206 || response.Body.String() != "cdefghi" {
		t.Fatalf("invalid resumed response: %d %q", response.Code, response.Body.String())
	}
}

func TestLimitsEachPeer(t *testing.T) {
	s := New(nil)
	for i := 0; i < 240; i++ {
		if !s.allow("192.0.2.1") {
			t.Fatalf("request %d limited prematurely", i+1)
		}
	}
	if s.allow("192.0.2.1") || !s.allow("192.0.2.2") {
		t.Fatal("rate limiter did not isolate peers")
	}
}

func TestDecodesPythonMongoMetadata(t *testing.T) {
	reference := []byte{0, 255, 32}
	payload, err := bson.Marshal(bson.M{
		"bot_id": "1", "filename": "fixture.mp4", "mime_type": "video/mp4", "unique_id": "unique",
		"media": bson.M{"dc": 2, "kind": "document", "id": int64(31415926535), "access_hash": int64(-27182818284),
			"size": int64(1 << 32), "file_reference": reference},
	})
	if err != nil {
		t.Fatal(err)
	}
	var record metadata
	if err := bson.Unmarshal(payload, &record); err != nil {
		t.Fatal(err)
	}
	if record.BotID != "1" || record.Media.DC != 2 || record.Media.ID != 31415926535 ||
		record.Media.Hash != -27182818284 || record.Media.Size != 1<<32 || !bytes.Equal(record.Media.Reference, reference) {
		t.Fatalf("unexpected decoded media metadata: %+v", record)
	}
}
