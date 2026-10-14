// Package frisbiiwebhook verifies Frisbii (Reepay) webhook signatures. Standard library only.
// signature = hex(HMAC_SHA256(key = webhookSecret, message = timestamp + id))
package frisbiiwebhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

// Payload holds the fields needed for verification; decode the request body into it.
type Payload struct {
	ID        string `json:"id"`
	EventID   string `json:"event_id"`
	EventType string `json:"event_type"`
	Timestamp string `json:"timestamp"`
	Signature string `json:"signature"`
}

func ComputeSignature(secret, timestamp, id string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(timestamp + id))
	return hex.EncodeToString(mac.Sum(nil))
}

func Verify(p Payload, secret string) bool {
	if p.ID == "" || p.Timestamp == "" || p.Signature == "" {
		return false
	}
	expected := ComputeSignature(secret, p.Timestamp, p.ID)
	return hmac.Equal([]byte(expected), []byte(strings.ToLower(p.Signature)))
}
