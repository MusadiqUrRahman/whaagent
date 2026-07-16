package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadConfig_ValidConfig(t *testing.T) {
	// Create a temporary config file
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, ".whaagent.yaml")
	configContent := `
api:
  host: 127.0.0.1
  port: 8000
whatsapp:
  tenants:
    - id: personal
      phone: "+34611111111"
      default_agent: developer
      allowed_contacts: []
    - id: work
      phone: "+34622222222"
      default_agent: chef
      allowed_contacts:
        - "+34633333333"
storage:
  base_path: ~/.local/share/whaagent
`
	if err := os.WriteFile(configPath, []byte(configContent), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	// Load config
	config, err := LoadConfig(configPath)
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	// Verify API config
	if config.API.Host != "127.0.0.1" {
		t.Errorf("expected host '127.0.0.1', got '%s'", config.API.Host)
	}
	if config.API.Port != 8000 {
		t.Errorf("expected port 8000, got %d", config.API.Port)
	}

	// Verify WhatsApp tenants
	if len(config.WhatsApp.Tenants) != 2 {
		t.Fatalf("expected 2 tenants, got %d", len(config.WhatsApp.Tenants))
	}

	// Check first tenant
	tenant1 := config.WhatsApp.Tenants[0]
	if tenant1.ID != "personal" {
		t.Errorf("expected tenant ID 'personal', got '%s'", tenant1.ID)
	}
	if tenant1.Phone != "+34611111111" {
		t.Errorf("expected phone '+34611111111', got '%s'", tenant1.Phone)
	}
	if tenant1.DefaultAgent != "developer" {
		t.Errorf("expected default_agent 'developer', got '%s'", tenant1.DefaultAgent)
	}
	if len(tenant1.AllowedContacts) != 0 {
		t.Errorf("expected 0 allowed contacts, got %d", len(tenant1.AllowedContacts))
	}

	// Check second tenant
	tenant2 := config.WhatsApp.Tenants[1]
	if tenant2.ID != "work" {
		t.Errorf("expected tenant ID 'work', got '%s'", tenant2.ID)
	}
	if len(tenant2.AllowedContacts) != 1 {
		t.Errorf("expected 1 allowed contact, got %d", len(tenant2.AllowedContacts))
	}
	if tenant2.AllowedContacts[0] != "+34633333333" {
		t.Errorf("expected allowed contact '+34633333333', got '%s'", tenant2.AllowedContacts[0])
	}

	// Verify storage config - tilde should be expanded to home directory
	homeDir, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get home directory: %v", err)
	}
	expectedPath := homeDir + "/.local/share/whaagent"
	if config.Storage.BasePath != expectedPath {
		t.Errorf("expected base_path '%s', got '%s'", expectedPath, config.Storage.BasePath)
	}
}

func TestLoadConfig_TildeExpansion(t *testing.T) {
	// Create a temporary config file with tilde path
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, ".whaagent.yaml")
	configContent := `
whatsapp:
  tenants:
    - id: personal
      phone: "+34611111111"
      default_agent: developer
      allowed_contacts: []
storage:
  base_path: ~/custom/path
`
	if err := os.WriteFile(configPath, []byte(configContent), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	config, err := LoadConfig(configPath)
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	homeDir, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get home directory: %v", err)
	}

	expectedPath := homeDir + "/custom/path"
	if config.Storage.BasePath != expectedPath {
		t.Errorf("expected expanded path '%s', got '%s'", expectedPath, config.Storage.BasePath)
	}

	// Verify no tilde remains in the path
	if config.Storage.BasePath[:1] == "~" {
		t.Errorf("tilde was not expanded, got '%s'", config.Storage.BasePath)
	}
}

func TestLoadConfig_GetAPIKey(t *testing.T) {
	// Create a temporary config file with auth
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, ".whaagent.yaml")
	configContent := `
auth:
  api_keys:
    "test-key-123": "personal"
whatsapp:
  tenants:
    - id: personal
      phone: "+34611111111"
      default_agent: developer
      allowed_contacts: []
`
	if err := os.WriteFile(configPath, []byte(configContent), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	config, err := LoadConfig(configPath)
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	apiKey := config.GetAPIKey()
	if apiKey != "test-key-123" {
		t.Errorf("expected API key 'test-key-123', got '%s'", apiKey)
	}
}

func TestLoadConfig_GetAPIKey_Empty(t *testing.T) {
	config := &Config{
		Auth: AuthConfig{
			APIKeys: map[string]string{},
		},
	}

	apiKey := config.GetAPIKey()
	if apiKey != "" {
		t.Errorf("expected empty API key, got '%s'", apiKey)
	}
}

func TestLoadConfig_MissingDefaults(t *testing.T) {
	// Create a minimal config file
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, ".whaagent.yaml")
	configContent := `
whatsapp:
  tenants:
    - id: personal
      phone: "+34611111111"
      default_agent: developer
      allowed_contacts: []
`
	if err := os.WriteFile(configPath, []byte(configContent), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	// Load config
	config, err := LoadConfig(configPath)
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	// Verify defaults are applied
	if config.API.Host != "127.0.0.1" {
		t.Errorf("expected default host '127.0.0.1', got '%s'", config.API.Host)
	}
	if config.API.Port != 8000 {
		t.Errorf("expected default port 8000, got %d", config.API.Port)
	}

	// Verify storage path has a default (should be expanded home dir)
	if config.Storage.BasePath == "" {
		t.Error("expected default storage base_path, got empty string")
	}
}

func TestLoadConfig_FileNotFound(t *testing.T) {
	configPath := "/nonexistent/.whaagent.yaml"
	_, err := LoadConfig(configPath)
	if err == nil {
		t.Error("expected error for nonexistent file, got nil")
	}
}

func TestLoadConfig_InvalidYAML(t *testing.T) {
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, ".whaagent.yaml")
	invalidYAML := `
api:
  host: 127.0.0.1
  port: [invalid
`
	if err := os.WriteFile(configPath, []byte(invalidYAML), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	_, err := LoadConfig(configPath)
	if err == nil {
		t.Error("expected error for invalid YAML, got nil")
	}
}

func TestGetTenantByID(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "personal", Phone: "+34611111111", DefaultAgent: "developer"},
				{ID: "work", Phone: "+34622222222", DefaultAgent: "chef"},
			},
		},
	}

	// Test existing tenant
	tenant, err := config.GetTenantByID("personal")
	if err != nil {
		t.Errorf("GetTenantByID failed: %v", err)
	}
	if tenant.ID != "personal" {
		t.Errorf("expected tenant ID 'personal', got '%s'", tenant.ID)
	}
	if tenant.Phone != "+34611111111" {
		t.Errorf("expected phone '+34611111111', got '%s'", tenant.Phone)
	}

	// Test non-existing tenant
	_, err = config.GetTenantByID("nonexistent")
	if err == nil {
		t.Error("expected error for non-existing tenant, got nil")
	}
}

func TestValidate_ValidConfig(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "personal", Phone: "+34611111111", DefaultAgent: "developer"},
				{ID: "work", Phone: "+34622222222", DefaultAgent: "chef"},
			},
		},
	}

	err := config.Validate()
	if err != nil {
		t.Errorf("Validate failed for valid config: %v", err)
	}
}

func TestValidate_NoTenants(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{},
		},
	}

	err := config.Validate()
	if err == nil {
		t.Error("expected error for config with no tenants, got nil")
	}
}

func TestValidate_EmptyTenantID(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "", Phone: "+34611111111", DefaultAgent: "developer"},
			},
		},
	}

	err := config.Validate()
	if err == nil {
		t.Error("expected error for tenant with empty ID, got nil")
	}
}

func TestValidate_EmptyPhone(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "personal", Phone: "", DefaultAgent: "developer"},
			},
		},
	}

	err := config.Validate()
	if err == nil {
		t.Error("expected error for tenant with empty phone, got nil")
	}
}

func TestValidate_EmptyDefaultAgent(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "personal", Phone: "+34611111111", DefaultAgent: ""},
			},
		},
	}

	err := config.Validate()
	if err == nil {
		t.Error("expected error for tenant with empty default_agent, got nil")
	}
}

func TestValidate_DuplicateTenantID(t *testing.T) {
	config := &Config{
		WhatsApp: WhatsAppConfig{
			Tenants: []TenantConfig{
				{ID: "personal", Phone: "+34611111111", DefaultAgent: "developer"},
				{ID: "personal", Phone: "+34622222222", DefaultAgent: "chef"},
			},
		},
	}

	err := config.Validate()
	if err == nil {
		t.Error("expected error for duplicate tenant IDs, got nil")
	}
}
