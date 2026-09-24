/**
 * Stable, lowercase UserError strings raised by contracts/Datum.py --
 * kept in exact sync with contracts/datum_lib.py's USER_ERRORS map so the
 * UI can show an honest, specific reason instead of a generic failure.
 */
export const USER_ERROR_MESSAGES: Record<string, string> = {
  "event not found": "That event id does not exist on this contract.",
  "not open": "This event is not open for that action anymore.",
  "already accepted": "This event already has a counterparty.",
  "window not closed": "The observation window has not closed yet.",
  "below min lead": "The window starts too soon (below the class minimum lead time).",
  "below min window": "The window is shorter than this class's minimum.",
  "unknown class": "That is not a supported DATUM instrument class.",
  "unknown station": "That is not a recognized official station id or bbox.",
  "unknown publisher": "That publisher is not on this class's locked allowlist.",
  "single publisher": "At least two independent publishers are required.",
  "stake mismatch": "The attached GEN does not match what this action requires.",
  "not a party": "Only a bonded party to this event can do that.",
  "nothing to claim": "There is nothing owed to this address.",
  "appeal closed": "The appeal window for this event has closed.",
  "not pending": "This event is not in the right state for that action.",
};

export function describeUserError(message: string): string {
  const normalized = message.trim().toLowerCase();
  return USER_ERROR_MESSAGES[normalized] ?? message;
}
