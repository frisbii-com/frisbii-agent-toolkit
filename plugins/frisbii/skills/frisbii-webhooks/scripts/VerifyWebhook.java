// Verify a Frisbii (Reepay) webhook signature. JDK only.
// signature = hex(HMAC_SHA256(key = webhookSecret, message = timestamp + id))
// Parse the JSON body with your usual library and pass the three string fields.
// Pass timestamp as the raw string: mapping it to OffsetDateTime/Instant and back
// changes the text and the signature no longer matches.

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class VerifyWebhook {

    private VerifyWebhook() {}

    public static String computeSignature(String secret, String timestamp, String id) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        byte[] digest = mac.doFinal((timestamp + id).getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            hex.append(String.format("%02x", b));
        }
        return hex.toString();
    }

    public static boolean verify(String secret, String timestamp, String id, String signature) {
        if (timestamp == null || id == null || signature == null) {
            return false;
        }
        try {
            byte[] expected = computeSignature(secret, timestamp, id).getBytes(StandardCharsets.UTF_8);
            byte[] actual = signature.toLowerCase().getBytes(StandardCharsets.UTF_8);
            return MessageDigest.isEqual(expected, actual);
        } catch (Exception e) {
            return false;
        }
    }
}
