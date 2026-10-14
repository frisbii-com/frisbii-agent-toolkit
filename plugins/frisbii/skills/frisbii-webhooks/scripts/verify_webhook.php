<?php
// Verify a Frisbii (Reepay) webhook signature. No dependencies.
// signature = hex(HMAC_SHA256(key = webhook secret, message = timestamp . id))
//
// $payload = json_decode(file_get_contents('php://input'), true);
// if (!verify_frisbii_webhook($payload, getenv('FRISBII_WEBHOOK_SECRET'))) { http_response_code(401); exit; }

function verify_frisbii_webhook($payload, string $secret): bool
{
    if (!is_array($payload)
        || !is_string($payload['timestamp'] ?? null)
        || !is_string($payload['id'] ?? null)
        || !is_string($payload['signature'] ?? null)) {
        return false;
    }
    $expected = hash_hmac('sha256', $payload['timestamp'] . $payload['id'], $secret);
    return hash_equals($expected, strtolower($payload['signature']));
}
