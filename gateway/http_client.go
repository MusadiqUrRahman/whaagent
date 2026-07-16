package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"

	"github.com/rs/zerolog"
)

// MessagePayload represents the payload sent to the Python API
type MessagePayload struct {
	From     string `json:"from"`
	Message  string `json:"message"`
	TenantID string `json:"tenant_id"`
}

// HTTPClient handles communication with the Python API
type HTTPClient struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
	logger     zerolog.Logger
}

// NewHTTPClient creates a new HTTP client for API communication
func NewHTTPClient(baseURL string, apiKey string) *HTTPClient {
	return &HTTPClient{
		baseURL: baseURL,
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 5 * time.Minute, // Fail fast on rate-limited or stuck LLM calls
		},
	}
}

// SendQRCode sends a QR code to the Python API
func (c *HTTPClient) SendQRCode(tenantID string, base64Image string) error {
	payload := map[string]string{
		"image": base64Image,
	}

	return c.post(fmt.Sprintf("/api/v1/whatsapp/qr/%s", tenantID), payload)
}

// SendConnectedStatus sends connected status to the Python API
func (c *HTTPClient) SendConnectedStatus(tenantID string, phone string) error {
	payload := map[string]string{
		"status": "connected",
		"phone":  phone,
	}

	return c.post(fmt.Sprintf("/api/v1/whatsapp/status/%s", tenantID), payload)
}

// SendDisconnectedStatus sends disconnected status to the Python API
func (c *HTTPClient) SendDisconnectedStatus(tenantID string) error {
	payload := map[string]string{
		"status": "disconnected",
	}

	return c.post(fmt.Sprintf("/api/v1/whatsapp/status/%s", tenantID), payload)
}

// apiResponse represents the JSON response from the Python API
type apiResponse struct {
	Response        string `json:"response"`
	TenantID        string `json:"tenant_id"`
	WakeWordMatched string `json:"wake_word_matched,omitempty"` // "true" or "false" for audio messages
}

// ForwardMessage forwards a message to the Python API and returns the agent's text response.
// The Python API returns {"response": "...", "tenant_id": "..."} — only the response field is extracted.
func (c *HTTPClient) ForwardMessage(tenantID string, phone string, messageText string) (string, error) {
	url := fmt.Sprintf("%s/api/v1/channels/whatsapp/message", c.baseURL)

	payload := MessagePayload{
		From:     phone,
		Message:  messageText,
		TenantID: tenantID,
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal payload: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewReader(jsonPayload))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	// Add API key header
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected status code %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response body: %w", err)
	}

	var apiResp apiResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return "", fmt.Errorf("failed to parse API response: %w", err)
	}

	if apiResp.Response == "" {
		return "", fmt.Errorf("empty response from API")
	}

	return apiResp.Response, nil
}

// AudioResponse holds the result of forwarding an audio message.
type AudioResponse struct {
	Response        string
	WakeWordMatched bool // true when the audio contained the wake word
}

// ForwardAudioMessage sends audio data to the Python API for transcription and agent processing.
func (c *HTTPClient) ForwardAudioMessage(tenantID string, phone string, audioData []byte, mimeType string) (AudioResponse, error) {
	url := fmt.Sprintf("%s/api/v1/channels/whatsapp/audio", c.baseURL)

	// Build multipart form
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	// Add audio file
	part, err := writer.CreateFormFile("audio", "voice_message.ogg")
	if err != nil {
		return AudioResponse{}, fmt.Errorf("failed to create multipart form: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return AudioResponse{}, fmt.Errorf("failed to write audio data: %w", err)
	}

	// Add metadata fields
	_ = writer.WriteField("tenant_id", tenantID)
	_ = writer.WriteField("phone", phone)
	_ = writer.WriteField("mime_type", mimeType)
	writer.Close()

	req, err := http.NewRequest("POST", url, &buf)
	if err != nil {
		return AudioResponse{}, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", writer.FormDataContentType())
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return AudioResponse{}, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return AudioResponse{}, fmt.Errorf("unexpected status code %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return AudioResponse{}, fmt.Errorf("failed to read response body: %w", err)
	}

	var apiResp apiResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return AudioResponse{}, fmt.Errorf("failed to parse API response: %w", err)
	}

	wakeMatched := apiResp.WakeWordMatched != "false"
	return AudioResponse{
		Response:        apiResp.Response,
		WakeWordMatched: wakeMatched,
	}, nil
}

// post sends a POST request to the Python API
func (c *HTTPClient) post(path string, payload interface{}) error {
	url := c.baseURL + path

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	resp, err := c.httpClient.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status code %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}
