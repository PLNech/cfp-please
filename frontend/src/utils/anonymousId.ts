/**
 * Anonymous User ID - High-cardinality local identifier
 *
 * Generates a unique anonymous user ID for Agent Studio conversation tracking.
 * Stored in localStorage for persistence across sessions.
 *
 * Design:
 * - 64-bit hex string (16 chars) = ~1.8×10^19 possible values
 * - Under 1M users: collision probability < 0.00001% (birthday paradox)
 * - Prefixed with 'cfp_' for easy identification in dashboards
 */

const STORAGE_KEY = 'cfp_anon_user_id';

/**
 * Generate a cryptographically random hex string
 */
function generateRandomHex(bytes: number): string {
  const array = new Uint8Array(bytes);
  crypto.getRandomValues(array);
  return Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Get or create anonymous user ID
 * Returns stable ID across sessions (stored in localStorage)
 */
export function getAnonymousUserId(): string {
  // Check localStorage first
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    return stored;
  }

  // Generate new ID: cfp_ + 16 hex chars (64 bits)
  const newId = `cfp_${generateRandomHex(8)}`;

  // Persist
  localStorage.setItem(STORAGE_KEY, newId);

  return newId;
}

/**
 * Generate a unique message ID
 * Format: msg_{timestamp}_{random}
 */
export function generateMessageId(): string {
  return `msg_${Date.now()}_${generateRandomHex(4)}`;
}

/**
 * Generate a unique conversation ID
 * Format: conv_{userId}_{timestamp}_{random}
 */
export function generateConversationId(): string {
  const userId = getAnonymousUserId();
  return `conv_${userId}_${Date.now()}_${generateRandomHex(4)}`;
}
