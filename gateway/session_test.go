package main

import (
	"context"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/rs/zerolog"
)

func TestNewSessionManager(t *testing.T) {
	// Create temporary directory for testing
	tmpDir, err := os.MkdirTemp("", "whaagent-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	config := &Config{
		Storage: StorageConfig{
			BasePath: tmpDir,
		},
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{
					ID:           "test-tenant",
					Phone:        "+1234567890",
					DefaultAgent: "developer",
				},
			},
		},
	}

	logger := zerolog.New(os.Stdout)

	sm, err := NewSessionManager(config, logger)
	if err != nil {
		t.Fatalf("Failed to create session manager: %v", err)
	}

	if sm == nil {
		t.Fatal("Session manager is nil")
	}

	if sm.storeDir != filepath.Join(tmpDir, "tenants") {
		t.Errorf("Expected storeDir %s, got %s", filepath.Join(tmpDir, "tenants"), sm.storeDir)
	}
}

func TestSessionManager_ConcurrentAccess(t *testing.T) {
	// Create temporary directory for testing
	tmpDir, err := os.MkdirTemp("", "whaagent-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	config := &Config{
		Storage: StorageConfig{
			BasePath: tmpDir,
		},
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "tenant1", Phone: "+1234567890", DefaultAgent: "developer"},
				{ID: "tenant2", Phone: "+0987654321", DefaultAgent: "chef"},
			},
		},
	}

	logger := zerolog.New(os.Stdout)

	sm, err := NewSessionManager(config, logger)
	if err != nil {
		t.Fatalf("Failed to create session manager: %v", err)
	}

	// Test concurrent reads
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sm.mu.RLock()
			time.Sleep(10 * time.Millisecond)
			sm.mu.RUnlock()
		}()
	}

	wg.Wait()
}

func TestSessionManager_GetClient_NotFound(t *testing.T) {
	// Create temporary directory for testing
	tmpDir, err := os.MkdirTemp("", "whaagent-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	config := &Config{
		Storage: StorageConfig{
			BasePath: tmpDir,
		},
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "test-tenant", Phone: "+1234567890", DefaultAgent: "developer"},
			},
		},
	}

	logger := zerolog.New(os.Stdout)

	sm, err := NewSessionManager(config, logger)
	if err != nil {
		t.Fatalf("Failed to create session manager: %v", err)
	}

	_, err = sm.GetClient("non-existent")
	if err == nil {
		t.Error("Expected error for non-existent client, got nil")
	}
}

func TestGenerateQRCodePNG(t *testing.T) {
	testCode := "test123456789"

	base64Img, err := GenerateQRCodePNG(testCode)
	if err != nil {
		t.Fatalf("Failed to generate QR code: %v", err)
	}

	if base64Img == "" {
		t.Error("Generated QR code is empty")
	}

	// Verify it's a valid base64 string
	// Base64 should only contain specific characters
	for _, c := range base64Img {
		if !((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
			c == '+' || c == '/' || c == '=') {
			t.Errorf("Invalid base64 character: %c", c)
		}
	}
}

func TestSessionManager_StopAll(t *testing.T) {
	// Create temporary directory for testing
	tmpDir, err := os.MkdirTemp("", "whaagent-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	config := &Config{
		Storage: StorageConfig{
			BasePath: tmpDir,
		},
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "tenant1", Phone: "+1234567890", DefaultAgent: "developer"},
			},
		},
	}

	logger := zerolog.New(os.Stdout)

	sm, err := NewSessionManager(config, logger)
	if err != nil {
		t.Fatalf("Failed to create session manager: %v", err)
	}

	ctx := context.Background()

	// StopAll should not fail even with no sessions
	if err := sm.StopAll(ctx); err != nil {
		t.Errorf("StopAll failed: %v", err)
	}
}
