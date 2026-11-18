package uphoster

import (
	"amaterasu/go-engine/internal/ipc"

	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type hostUpload struct {
	Provider, URL, Path, Field, Filename, Authorization string
	Fields                                              map[string]string
}

func (h hostUpload) target() (*url.URL, bool) {
	domains := map[string]string{
		"gofile": "gofile.io", "pixeldrain": "pixeldrain.com",
		"buzzheavier": "buzzheavier.com", "devuploads": "devuploads.com",
		"vikingfile": "vikingfile.com",
	}
	target, err := url.Parse(h.URL)
	domain := domains[h.Provider]
	if err != nil || domain == "" || target.Scheme != "https" || target.User != nil ||
		(target.Port() != "" && target.Port() != "443") || !filepath.IsAbs(h.Path) ||
		strings.ContainsAny(h.Filename, "\r\n") || strings.ContainsAny(h.Field, "\r\n") {
		return nil, false
	}
	for name := range h.Fields {
		if strings.ContainsAny(name, "\r\n") {
			return nil, false
		}
	}
	host := strings.ToLower(target.Hostname())
	return target, host == domain || strings.HasSuffix(host, "."+domain)
}

var hostHTTP = &http.Client{
	Timeout:       time.Hour,
	CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
}

type hostProgress struct {
	input          io.Reader
	updates        *ipc.TransferEvents
	current, total int64
}

func (p *hostProgress) Read(buffer []byte) (int, error) {
	n, err := p.input.Read(buffer)
	if n > 0 {
		p.current += int64(n)
		if progressErr := p.updates.Progress(p.current, p.total); progressErr != nil {
			return n, progressErr
		}
	}
	return n, err
}

func (h hostUpload) request(ctx context.Context, target *url.URL, file io.Reader, size int64) (*http.Request, error) {
	method, contentType := http.MethodPut, "application/octet-stream"
	if h.Field != "" {
		method = http.MethodPost
		var boundary bytes.Buffer
		form := multipart.NewWriter(&boundary)
		for name, value := range h.Fields {
			if err := form.WriteField(name, value); err != nil {
				return nil, err
			}
		}
		if _, err := form.CreateFormFile(h.Field, h.Filename); err != nil {
			return nil, err
		}
		split := boundary.Len()
		if err := form.Close(); err != nil {
			return nil, err
		}
		data := boundary.Bytes()
		file = io.MultiReader(bytes.NewReader(data[:split]), file, bytes.NewReader(data[split:]))
		size += int64(len(data))
		contentType = form.FormDataContentType()
	}
	req, err := http.NewRequestWithContext(ctx, method, target.String(), file)
	if err != nil {
		return nil, err
	}
	req.ContentLength = size
	req.Header.Set("Content-Type", contentType)
	if h.Authorization != "" {
		req.Header.Set("Authorization", h.Authorization)
	}
	return req, nil
}

func Upload(w http.ResponseWriter, r *http.Request) {
	var input hostUpload
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 64*1024)).Decode(&input); err != nil {
		http.Error(w, "invalid hoster request", http.StatusBadRequest)
		return
	}
	target, allowed := input.target()
	if !allowed {
		http.Error(w, "unsupported upload target", http.StatusBadRequest)
		return
	}
	file, err := os.Open(input.Path)
	if err != nil {
		http.Error(w, "unavailable upload file", http.StatusBadRequest)
		return
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() == 0 {
		http.Error(w, "invalid upload file", http.StatusBadRequest)
		return
	}
	updates := ipc.Events(w)
	req, err := input.request(r.Context(), target, &hostProgress{input: file, updates: updates, total: info.Size()}, info.Size())
	if err != nil {
		updates.Finish(nil, err)
		return
	}
	if err := updates.Progress(0, info.Size()); err != nil {
		return
	}
	res, err := hostHTTP.Do(req)
	if err != nil {
		updates.Finish(nil, err)
		return
	}
	defer res.Body.Close()
	const limit = 1024 * 1024
	body, err := io.ReadAll(io.LimitReader(res.Body, limit+1))
	if err != nil || len(body) > limit {
		updates.Finish(nil, errors.New("unreadable hoster response"))
		return
	}
	if err := updates.Progress(info.Size(), info.Size()); err != nil {
		return
	}
	updates.Finish(map[string]any{"code": res.StatusCode, "text": string(body)}, nil)
}
