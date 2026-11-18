package mtproto

import (
	"bytes"
	"context"
	"crypto/sha256"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gotd/td/bin"
	"github.com/gotd/td/telegram"
)

func TestSeekReturnsExactRangeAcrossChunks(t *testing.T) {
	source := bytes.Repeat([]byte("0123456789abcdefXYZ"), 120000)
	media := MediaRange{Start: chunkSize - 3, End: chunkSize + 16, Size: int64(len(source))}
	result := httptest.NewRecorder()
	serveRange(result, context.Background(), media, func(_ context.Context, offset int64) ([]byte, error) {
		return source[offset:min(offset+chunkSize, int64(len(source)))], nil
	})
	if result.Code != http.StatusPartialContent || result.Header().Get("Content-Length") != "20" ||
		result.Header().Get("Content-Range") != "bytes 1048573-1048592/2280000" ||
		!bytes.Equal(result.Body.Bytes(), source[media.Start:media.End+1]) {
		t.Fatalf("wrong range response: %d, %v, %q", result.Code, result.Header(), result.Body.Bytes())
	}
}

func TestTenMiBRangeConformance(t *testing.T) {
	source := bytes.Repeat([]byte("0123456789ab"), 2*1024*1024)
	media := MediaRange{Start: 10 * chunkSize, End: 20*chunkSize - 1, Size: int64(len(source))}
	result := httptest.NewRecorder()
	serveRange(result, context.Background(), media, func(_ context.Context, offset int64) ([]byte, error) {
		return source[offset:min(offset+chunkSize, int64(len(source)))], nil
	})
	if result.Code != 206 || result.Header().Get("Content-Length") != "10485760" ||
		result.Header().Get("Content-Range") != fmt.Sprintf("bytes 10485760-20971519/%d", len(source)) ||
		sha256.Sum256(result.Body.Bytes()) != sha256.Sum256(source[media.Start:media.End+1]) {
		t.Fatalf("invalid 10 MiB response: %d %v", result.Code, result.Header())
	}
}

func BenchmarkRange10MiB(b *testing.B) {
	chunk := make([]byte, chunkSize)
	b.SetBytes(10 * chunkSize)
	for i := 0; i < b.N; i++ {
		for result := range rangeChunks(context.Background(), 0, 10*chunkSize-1,
			func(context.Context, int64) ([]byte, error) { return chunk, nil }) {
			if result.err != nil {
				b.Fatal(result.err)
			}
		}
	}
}

func TestShortFirstChunkProducesBadGateway(t *testing.T) {
	result := httptest.NewRecorder()
	serveRange(result, context.Background(), MediaRange{Size: 10, End: 5}, func(context.Context, int64) ([]byte, error) {
		return []byte("short"), nil
	})
	if result.Code != http.StatusBadGateway {
		t.Fatalf("expected a failure before sending media, got %d", result.Code)
	}
}

func TestRangeCancellationStopsProducer(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	chunks := rangeChunks(ctx, 0, 10, func(ctx context.Context, _ int64) ([]byte, error) {
		<-ctx.Done()
		return nil, ctx.Err()
	})
	cancel()
	timer := time.After(time.Second)
	for {
		select {
		case _, ok := <-chunks:
			if !ok {
				return
			}
		case <-timer:
			t.Fatal("range producer survived cancellation")
		}
	}
}

func TestRangePrefetchesConcurrentlyAndSendsInOrder(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	first := make(chan struct{})
	started := make(chan int64, 4)
	chunks := rangeChunks(ctx, chunkSize-1, 2*chunkSize, func(ctx context.Context, offset int64) ([]byte, error) {
		started <- offset
		if offset == 0 {
			select {
			case <-first:
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}
		return bytes.Repeat([]byte{byte(offset / chunkSize)}, chunkSize), nil
	})
	for i := 0; i < 3; i++ {
		select {
		case <-started:
		case <-ctx.Done():
			t.Fatal("later chunks did not start while the first was blocked")
		}
	}
	close(first)
	var output []byte
	for chunk := range chunks {
		if chunk.err != nil {
			t.Fatal(chunk.err)
		}
		output = append(output, chunk.data...)
	}
	if len(output) != chunkSize+2 || output[0] != 0 ||
		!bytes.Equal(output[1:len(output)-1], bytes.Repeat([]byte{1}, chunkSize)) ||
		output[len(output)-1] != 2 {
		t.Fatal("prefetch emitted the wrong bytes or order")
	}
}

type testPool struct{}

func (*testPool) Close() error                                           { return nil }
func (*testPool) Invoke(context.Context, bin.Encoder, bin.Decoder) error { return nil }

func TestMediaClientReusesWorkerPool(t *testing.T) {
	pool := &testPool{}
	w := &worker{done: make(chan struct{}), pools: map[int]telegram.CloseInvoker{2: pool}}
	for i := 0; i < 2; i++ {
		client, err := w.mediaClient(context.Background(), 2)
		if err != nil || client.Invoker() != pool {
			t.Fatalf("pool reuse failed: %v", err)
		}
	}
}

func TestFirstChunkFloodWaitIsReported(t *testing.T) {
	result := httptest.NewRecorder()
	serveRange(result, context.Background(), MediaRange{Size: 10, End: 5}, func(context.Context, int64) ([]byte, error) {
		return nil, &floodError{until: time.Now().Add(60 * time.Second)}
	})
	if result.Code != http.StatusTooManyRequests || result.Header().Get("Retry-After") != "60" {
		t.Fatalf("missing flood wait response: %d %v", result.Code, result.Header())
	}
}
