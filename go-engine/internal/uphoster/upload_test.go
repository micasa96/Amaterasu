package uphoster

import (
	"bytes"
	"context"
	"io"
	"path/filepath"
	"strings"
	"testing"
)

func TestHosterMultipartAndTargetValidation(t *testing.T) {
	input := hostUpload{
		Provider: "gofile", URL: "https://upload.gofile.io/uploadfile",
		Path: filepath.Join(t.TempDir(), "video"), Field: "file", Filename: "video.bin",
		Fields: map[string]string{"folderId": "folder"},
	}
	target, ok := input.target()
	if !ok {
		t.Fatal("valid upload host rejected")
	}
	payload := "test payload"
	request, err := input.request(context.Background(), target, strings.NewReader(payload), int64(len(payload)))
	if err != nil {
		t.Fatal(err)
	}
	wire, err := io.ReadAll(request.Body)
	if err != nil || request.ContentLength != int64(len(wire)) || request.Method != "POST" {
		t.Fatalf("invalid HTTP body framing: %v", err)
	}
	request.Body = io.NopCloser(bytes.NewReader(wire))
	reader, err := request.MultipartReader()
	if err != nil {
		t.Fatal(err)
	}
	for _, expect := range []struct{ field, value string }{{"folderId", "folder"}, {"file", payload}} {
		part, err := reader.NextPart()
		if err != nil {
			t.Fatal(err)
		}
		got, err := io.ReadAll(part)
		if err != nil || part.FormName() != expect.field || string(got) != expect.value {
			t.Fatalf("wrong multipart field or value: %v", err)
		}
	}
	input.URL = "https://gofile.io.example.com"
	if _, ok := input.target(); ok {
		t.Fatal("unrelated upload host accepted")
	}
}
