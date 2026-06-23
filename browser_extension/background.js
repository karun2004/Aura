/**
 * AURA Browser Bridge — background service worker.
 *
 * Maintains a WebSocket connection to the local AURA Python backend,
 * relays tab information and page content requests.
 *
 * TODO: implement (Goals 9, 10)
 */

const AURA_WS_URL = "ws://localhost:8765";

console.log("[AURA] Browser bridge loaded (not yet connected)");
