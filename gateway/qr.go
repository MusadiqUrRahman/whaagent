package main

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"image/png"

	"github.com/skip2/go-qrcode"
)

// GenerateQRCodePNG generates a QR code PNG image from the given code string
func GenerateQRCodePNG(code string) (string, error) {
	// Generate QR code with recommended size for WhatsApp
	qr, err := qrcode.New(code, qrcode.Medium)
	if err != nil {
		return "", fmt.Errorf("failed to create QR code: %w", err)
	}

	// Create PNG buffer
	var buf bytes.Buffer

	// Generate QR code as PNG (256x256 is a good size for scanning)
	if err := png.Encode(&buf, qr.Image(256)); err != nil {
		return "", fmt.Errorf("failed to encode QR code as PNG: %w", err)
	}

	// Encode to base64
	base64Str := base64.StdEncoding.EncodeToString(buf.Bytes())

	return base64Str, nil
}
