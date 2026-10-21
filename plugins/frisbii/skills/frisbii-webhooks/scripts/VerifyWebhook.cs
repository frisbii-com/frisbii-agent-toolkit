// Verify a Frisbii (Reepay) webhook signature. .NET BCL only.
// signature = hex(HMAC_SHA256(key = webhookSecret, message = timestamp + id))
// Pass timestamp as the raw string. System.Text.Json's GetString() keeps it as is;
// Newtonsoft JObject parses ISO dates by default and changes the text, so load it
// with DateParseHandling.None.

using System;
using System.Security.Cryptography;
using System.Text;

public static class FrisbiiWebhook
{
    public static string ComputeSignature(string secret, string timestamp, string id)
    {
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        var digest = hmac.ComputeHash(Encoding.UTF8.GetBytes(timestamp + id));
        return Convert.ToHexString(digest).ToLowerInvariant();
    }

    public static bool Verify(string secret, string? timestamp, string? id, string? signature)
    {
        if (timestamp is null || id is null || signature is null) return false;
        var expected = Encoding.UTF8.GetBytes(ComputeSignature(secret, timestamp, id));
        var actual = Encoding.UTF8.GetBytes(signature.ToLowerInvariant());
        return CryptographicOperations.FixedTimeEquals(expected, actual);
    }
}
