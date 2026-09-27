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

/**
 * estimateTransactionFeesForWrite() runs every write as a dry-run
 * simulation first. When contracts/Datum.py raises gl.vm.UserError(...)
 * during that simulation, genlayer-js/viem surface it as a generic
 * InvalidInputRpcError ("Missing or invalid parameters. Double check you
 * have provided the correct parameters.") instead of the real reason --
 * this happens for almost every legitimate rejection (wrong state, wrong
 * caller, wrong side, a stale event id), not just malformed calls, so it
 * was hitting users on ordinary action after ordinary action.
 *
 * The actual message survives inside err.cause.data.receipt.result: a
 * base64 blob whose first byte is GenVM's calldata type tag for "string"
 * (0x01) followed by the raw UTF-8 text. Every UserError this contract
 * raises is a plain string, so that one tag is all this needs to handle.
 * Confirmed live against the deployed contract across five distinct
 * rejections (wrong side, wrong caller, wrong state, nonexistent event,
 * appeal-not-pending) -- all decode cleanly with this exact byte layout.
 */
export function extractContractRevertMessage(err: unknown): string | null {
  const cause = (err as { cause?: unknown } | null | undefined)?.cause;
  const resultB64 = (
    cause as { data?: { receipt?: { result?: unknown } } } | null | undefined
  )?.data?.receipt?.result;
  if (typeof resultB64 !== "string") return null;
  try {
    const bytes = Uint8Array.from(atob(resultB64), (c) => c.charCodeAt(0));
    if (bytes.length < 1 || bytes[0] !== 1) return null;
    return new TextDecoder("utf-8").decode(bytes.slice(1));
  } catch {
    return null;
  }
}
