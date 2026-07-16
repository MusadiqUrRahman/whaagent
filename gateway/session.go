package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
)

// SessionManager manages multiple WhatsApp tenant sessions
type SessionManager struct {
	config     *Config
	storeDir   string
	clients    map[string]*whatsmeow.Client
	handlers   map[string]*EventHandler
	containers map[string]*sqlstore.Container // per-tenant session storage
	mu         sync.RWMutex
	logger     zerolog.Logger
	httpClient *HTTPClient
}

// EventHandler handles WhatsApp events for a specific tenant
type EventHandler struct {
	tenantID string
	session  *whatsmeow.Client
	manager  *SessionManager
	logger   zerolog.Logger
}

// NewSessionManager creates a new session manager
func NewSessionManager(config *Config, logger zerolog.Logger) (*SessionManager, error) {
	storeDir := filepath.Join(config.Storage.BasePath, "tenants")
	if err := os.MkdirAll(storeDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create store directory: %w", err)
	}

	sm := &SessionManager{
		config:     config,
		storeDir:   storeDir,
		clients:    make(map[string]*whatsmeow.Client),
		handlers:   make(map[string]*EventHandler),
		containers: make(map[string]*sqlstore.Container),
		logger:     logger,
		httpClient: NewHTTPClient(getAPIURL(config), config.GetAPIKey()),
	}

	return sm, nil
}

// getContainer returns (or creates) a per-tenant sqlstore.Container.
func (sm *SessionManager) getContainer(tenantID string) (*sqlstore.Container, error) {
	if c, ok := sm.containers[tenantID]; ok {
		return c, nil
	}

	tenantDir := filepath.Join(sm.storeDir, tenantID)
	if err := os.MkdirAll(tenantDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create tenant store directory: %w", err)
	}

	dbPath := filepath.Join(tenantDir, "whatsapp_sessions.db") + "?_foreign_keys=on"
	container, err := sqlstore.New(context.Background(), "sqlite3", dbPath, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create sqlstore for tenant %s: %w", tenantID, err)
	}

	sm.containers[tenantID] = container
	return container, nil
}

// StartSession starts a WhatsApp session for a tenant
func (sm *SessionManager) StartSession(ctx context.Context, tenantID string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	// Check if session already exists
	if _, exists := sm.clients[tenantID]; exists {
		return fmt.Errorf("session for tenant '%s' already exists", tenantID)
	}

	// Verify tenant exists in config
	tenant, err := sm.config.GetTenantByID(tenantID)
	if err != nil {
		return fmt.Errorf("tenant not found: %w", err)
	}

	sm.logger.Info().
		Str("tenant_id", tenantID).
		Str("phone", tenant.Phone).
		Msg("Starting WhatsApp session")

	// Get per-tenant container (isolated SQLite DB)
	container, err := sm.getContainer(tenantID)
	if err != nil {
		return fmt.Errorf("failed to get container: %w", err)
	}

	// Try to reuse an existing device (preserves session across restarts)
	// or create a new one if none exists
	var deviceStore *store.Device
	existingDevices, err := container.GetAllDevices(context.Background())
	if err != nil {
		return fmt.Errorf("failed to get devices: %w", err)
	}

	if len(existingDevices) > 0 {
		deviceStore = existingDevices[0]
		sm.logger.Info().
			Str("tenant_id", tenantID).
			Msg("Reusing existing device session")
	} else {
		deviceStore = container.NewDevice()
		sm.logger.Info().
			Str("tenant_id", tenantID).
			Msg("Created new device session")
	}

	client := whatsmeow.NewClient(deviceStore, waLog.Stdout("Client", tenantID, os.Getenv("LOG_LEVEL") == "debug"))

	handler := &EventHandler{
		tenantID: tenantID,
		session:  client,
		manager:  sm,
		logger:   sm.logger.With().Str("tenant_id", tenantID).Logger(),
	}

	client.AddEventHandler(handler.handleEvent)

	// Connect to WhatsApp
	if err := client.Connect(); err != nil {
		return fmt.Errorf("failed to connect: %w", err)
	}

	sm.clients[tenantID] = client
	sm.handlers[tenantID] = handler

	sm.logger.Info().
		Str("tenant_id", tenantID).
		Msg("WhatsApp session started")

	return nil
}

// StopSession stops a WhatsApp session for a tenant
func (sm *SessionManager) StopSession(ctx context.Context, tenantID string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	return sm.stopSessionLocked(ctx, tenantID)
}

func (sm *SessionManager) stopSessionLocked(ctx context.Context, tenantID string) error {
	client, exists := sm.clients[tenantID]
	if !exists {
		return fmt.Errorf("session for tenant '%s' not found", tenantID)
	}

	client.Disconnect()
	sm.logger.Info().Str("tenant_id", tenantID).Msg("WhatsApp session stopped")

	delete(sm.clients, tenantID)
	delete(sm.handlers, tenantID)

	sm.logger.Info().Str("tenant_id", tenantID).Msg("Session cleaned up")
	return nil
}

// StopAll stops all active sessions
func (sm *SessionManager) StopAll(ctx context.Context) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	var firstErr error
	for tenantID := range sm.clients {
		if err := sm.stopSessionLocked(ctx, tenantID); err != nil && firstErr == nil {
			firstErr = err
			sm.logger.Error().Err(err).
				Str("tenant_id", tenantID).
				Msg("Error stopping session")
		}
	}
	return firstErr
}

// GetClient returns the WhatsApp client for a tenant
func (sm *SessionManager) GetClient(tenantID string) (*whatsmeow.Client, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	client, exists := sm.clients[tenantID]
	if !exists {
		return nil, fmt.Errorf("session for tenant '%s' not found", tenantID)
	}
	return client, nil
}

// handleEvent routes WhatsApp events to the appropriate handler
func (eh *EventHandler) handleEvent(rawEvt interface{}) {
	switch evt := rawEvt.(type) {
	case *events.Connected:
		eh.handleConnected(evt)
	case *events.Disconnected:
		eh.handleDisconnected(evt)
	case *events.Message:
		go eh.handleMessage(evt)
	case *events.UndecryptableMessage:
		eh.logger.Warn().
			Str("sender", evt.Info.Sender.String()).
			Str("chat", evt.Info.Chat.String()).
			Bool("is_from_me", evt.Info.IsFromMe).
			Bool("unavailable", evt.IsUnavailable).
			Str("decrypt_fail_mode", string(evt.DecryptFailMode)).
			Msg("Received undecryptable message — session keys may be stale, consider re-scanning QR")
	case *events.QR:
		eh.handleQRCode(evt)
	default:
		eh.logger.Debug().Type("event_type", evt).Msg("Unhandled WhatsApp event")
	}
}

// handleQRCode handles QR code events
func (eh *EventHandler) handleQRCode(evt *events.QR) {
	if len(evt.Codes) == 0 {
		return
	}

	eh.logger.Debug().Msg("Received QR code event")

	// Use the first QR code
	code := evt.Codes[0]

	// Generate QR code image
	pngData, err := GenerateQRCodePNG(code)
	if err != nil {
		eh.logger.Error().Err(err).Msg("Failed to generate QR code PNG")
		return
	}

	// Send to Python API
	if err := eh.manager.httpClient.SendQRCode(eh.tenantID, pngData); err != nil {
		eh.logger.Error().Err(err).Msg("Failed to send QR code to API")
	}
}

// handleConnected handles connected events
func (eh *EventHandler) handleConnected(evt *events.Connected) {
	if eh.session.Store.ID == nil {
		eh.logger.Warn().Msg("Connected but Store.ID is nil")
		return
	}
	phone := eh.session.Store.ID.ToNonAD().String()
	eh.logger.Info().Str("tenant_id", eh.tenantID).Msg("WhatsApp connected")

	// Send status to Python API
	if err := eh.manager.httpClient.SendConnectedStatus(eh.tenantID, phone); err != nil {
		eh.logger.Error().Err(err).Msg("Failed to send connected status to API")
	}
}

// handleDisconnected handles disconnected events
func (eh *EventHandler) handleDisconnected(evt *events.Disconnected) {
	eh.logger.Info().Msg("WhatsApp disconnected")

	// Send status to Python API
	if err := eh.manager.httpClient.SendDisconnectedStatus(eh.tenantID); err != nil {
		eh.logger.Error().Err(err).Msg("Failed to send disconnected status to API")
	}
}

// handleMessage handles incoming messages from WhatsApp
func (eh *EventHandler) handleMessage(evt *events.Message) {
	// Delegate to the message handling function directly
	handleMessage(eh, evt)
}
