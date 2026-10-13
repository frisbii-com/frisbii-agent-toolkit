// Verify a Frisbii (Reepay) webhook signature. Node.js, no dependencies.
// signature = hex(HMAC_SHA256(key = webhookSecret, message = timestamp + id))
//
// Express example:
//   app.post("/webhooks/frisbii", express.json(), (req, res) => {
//     if (!verifyFrisbiiWebhook(req.body, process.env.FRISBII_WEBHOOK_SECRET)) return res.sendStatus(401);
//     queue.push(req.body); res.sendStatus(200);
//   });

const crypto = require("crypto");

function computeSignature(secret, timestamp, id) {
  return crypto.createHmac("sha256", secret).update(timestamp + id, "utf8").digest("hex");
}

function verifyFrisbiiWebhook(payload, secret) {
  if (!payload || typeof payload.timestamp !== "string" || typeof payload.id !== "string" ||
      typeof payload.signature !== "string") {
    return false;
  }
  const expected = Buffer.from(computeSignature(secret, payload.timestamp, payload.id), "utf8");
  const actual = Buffer.from(payload.signature.toLowerCase(), "utf8");
  return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
}

module.exports = { computeSignature, verifyFrisbiiWebhook };
