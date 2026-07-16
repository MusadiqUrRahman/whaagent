package main

import (
	"encoding/json"
	"testing"
)

// Test_MessagePayload_JSON tests that the MessagePayload can be marshaled to JSON
func Test_MessagePayload_JSON(t *testing.T) {
	payload := MessagePayload{
		From:     "1234567890",
		Message:  "Hello, how are you?",
		TenantID: "test-tenant",
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		t.Errorf("Failed to marshal MessagePayload: %v", err)
	}

	expected := `{"from":"1234567890","message":"Hello, how are you?","tenant_id":"test-tenant"}`
	if string(jsonData) != expected {
		t.Errorf("Expected JSON '%s', got '%s'", expected, string(jsonData))
	}
}

// Test_MessagePayload_JSON_WithSpecialCharacters tests JSON marshaling with special characters
func Test_MessagePayload_JSON_WithSpecialCharacters(t *testing.T) {
	payload := MessagePayload{
		From:     "+1234567890",
		Message:  "Hello! How are you? 😊",
		TenantID: "test-tenant-123",
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		t.Errorf("Failed to marshal MessagePayload with special characters: %v", err)
	}

	expected := `{"from":"+1234567890","message":"Hello! How are you? 😊","tenant_id":"test-tenant-123"}`
	if string(jsonData) != expected {
		t.Errorf("Expected JSON '%s', got '%s'", expected, string(jsonData))
	}
}

// Test_MessagePayload_JSON_EmptyFields tests JSON marshaling with empty fields
func Test_MessagePayload_JSON_EmptyFields(t *testing.T) {
	payload := MessagePayload{
		From:     "",
		Message:  "",
		TenantID: "",
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		t.Errorf("Failed to marshal MessagePayload with empty fields: %v", err)
	}

	expected := `{"from":"","message":"","tenant_id":""}`
	if string(jsonData) != expected {
		t.Errorf("Expected JSON '%s', got '%s'", expected, string(jsonData))
	}
}

// Test_isSelfMessageForTesting_selfMessage tests that isSelfMessageForTesting returns true for self-messages
func Test_isSelfMessageForTesting_selfMessage(t *testing.T) {
	result := isSelfMessageForTesting(true, "1234567890@s.whatsapp.net", "1234567890@s.whatsapp.net")
	if !result {
		t.Errorf("Expected isSelfMessageForTesting to return true for self-messages, got false")
	}
}

// Test_isSelfMessageForTesting_selfMessageWithDevice tests that JIDs with device suffixes are matched correctly
func Test_isSelfMessageForTesting_selfMessageWithDevice(t *testing.T) {
	// Store.ID includes device suffix, Chat does not — should still match
	result := isSelfMessageForTesting(true, "1234567890@s.whatsapp.net", "1234567890.0:21@s.whatsapp.net")
	if !result {
		t.Errorf("Expected isSelfMessageForTesting to return true for self-message with device suffix, got false")
	}
}

// Test_isSelfMessageForTesting_nonSelfMessage tests that isSelfMessageForTesting returns false for non-self messages
func Test_isSelfMessageForTesting_nonSelfMessage(t *testing.T) {
	result := isSelfMessageForTesting(false, "other@s.whatsapp.net", "1234567890@s.whatsapp.net")
	if result {
		t.Errorf("Expected isSelfMessageForTesting to return false for non-self messages, got true")
	}
}

// Test_isSelfMessageForTesting_differentChat tests that isSelfMessageForTesting returns false for messages from different chats
func Test_isSelfMessageForTesting_differentChat(t *testing.T) {
	result := isSelfMessageForTesting(true, "different-group@s.whatsapp.net", "1234567890@s.whatsapp.net")
	if result {
		t.Errorf("Expected isSelfMessageForTesting to return false for messages from different chats, got true")
	}
}

// Test_isSelfMessageForTesting_LIDBasedJID tests that LID-based JIDs are NOT matched
// by the phone-based isSelfMessageForTesting helper (LID matching requires the full isSelfMessage)
func Test_isSelfMessageForTesting_LIDBasedJID(t *testing.T) {
	// LID-based chat JID won't match phone-based store ID via this helper
	result := isSelfMessageForTesting(true, "118657162162293@lid", "34677427318@s.whatsapp.net")
	if result {
		t.Errorf("Expected isSelfMessageForTesting to return false for LID vs phone mismatch, got true")
	}
}

// Test_normalizePhoneNumber tests JID normalization
func Test_normalizePhoneNumber(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"34677427318@s.whatsapp.net", "34677427318"},
		{"34677427318.0:21@s.whatsapp.net", "34677427318"},
		{"118657162162293@lid", "118657162162293"},
		{"REDACTED_PHONE", "34677427318"},
		{"34677427318", "34677427318"},
	}

	for _, tc := range tests {
		result := normalizePhoneNumber(tc.input)
		if result != tc.expected {
			t.Errorf("normalizePhoneNumber(%q) = %q, want %q", tc.input, result, tc.expected)
		}
	}
}

// MockMessage simulates a simplified Message struct for testing
type MockMessage struct {
	Conversation *string
}

func (m MockMessage) GetConversation() string {
	if m.Conversation != nil {
		return *m.Conversation
	}
	return ""
}

// Test_apiResponse_JSON_parse tests that the API response JSON is parsed correctly
func Test_apiResponse_JSON_parse(t *testing.T) {
	raw := `{"response":"Hello! I am your assistant.","tenant_id":"personal"}`
	var resp apiResponse
	if err := json.Unmarshal([]byte(raw), &resp); err != nil {
		t.Fatalf("Failed to parse API response: %v", err)
	}
	if resp.Response != "Hello! I am your assistant." {
		t.Errorf("Expected response 'Hello! I am your assistant.', got '%s'", resp.Response)
	}
	if resp.TenantID != "personal" {
		t.Errorf("Expected tenant_id 'personal', got '%s'", resp.TenantID)
	}
}

// Test_apiResponse_JSON_emptyResponse tests that empty response is handled
func Test_apiResponse_JSON_emptyResponse(t *testing.T) {
	raw := `{"response":"","tenant_id":"personal"}`
	var resp apiResponse
	if err := json.Unmarshal([]byte(raw), &resp); err != nil {
		t.Fatalf("Failed to parse API response: %v", err)
	}
	if resp.Response != "" {
		t.Errorf("Expected empty response, got '%s'", resp.Response)
	}
}
