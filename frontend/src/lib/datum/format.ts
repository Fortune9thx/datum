export const VALUE_SCALE = 100;

/** Must match datum_lib.py's APPEAL_BOND_FLOOR exactly (0.05 GEN, wei). */
export const APPEAL_BOND_FLOOR_WEI = 5n * 10n ** 16n;

/**
 * Mirrors datum_lib.appeal_bond_amount(one_side_stake): half of one
 * side's stake, floored at APPEAL_BOND_FLOOR. Takes a wei-like stake
 * (string/number, avoiding float precision loss) and returns wei.
 */
export function appealBondWei(oneSideStakeWei: string | number | null | undefined): bigint {
  const stake = BigInt(oneSideStakeWei ?? 0);
  const half = stake / 2n;
  return half > APPEAL_BOND_FLOOR_WEI ? half : APPEAL_BOND_FLOOR_WEI;
}

/** Formats a VALUE_SCALE-scaled integer (string or number) back to a decimal string. */
export function formatScaledValue(scaled: string | number | null | undefined): string {
  if (scaled === null || scaled === undefined) return "--";
  const n = typeof scaled === "string" ? Number(scaled) : scaled;
  if (!Number.isFinite(n)) return "--";
  return (n / VALUE_SCALE).toFixed(2);
}

/** Formats a wei-like 18-decimal GEN amount (string, to avoid precision loss) to a decimal string. */
export function formatGen(amountWei: string | number | null | undefined): string {
  if (amountWei === null || amountWei === undefined) return "0";
  try {
    const value = BigInt(amountWei);
    const whole = value / 10n ** 18n;
    const frac = value % 10n ** 18n;
    const fracStr = frac.toString().padStart(18, "0").slice(0, 4).replace(/0+$/, "");
    return fracStr ? `${whole}.${fracStr}` : `${whole}`;
  } catch {
    return "0";
  }
}

export function parseGenToWei(amount: string): string {
  const [whole, frac = ""] = amount.trim().split(".");
  const fracPadded = (frac + "0".repeat(18)).slice(0, 18);
  const wholeDigits = whole === "" ? "0" : whole;
  return (BigInt(wholeDigits) * 10n ** 18n + BigInt(fracPadded || "0")).toString();
}

/** Compact UTC window, e.g. "2026-09-24 06:00 → 2026-09-24 12:00". */
export function formatWindowCompact(window: [number, number] | null | undefined): string {
  if (!window) return "--";
  const at = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ");
  return `${at(window[0])} → ${at(window[1])}`;
}

export function formatThreshold(
  scaled: number | string | null | undefined,
  cmp: string,
  unit: string
): string {
  return `${cmp} ${formatScaledValue(scaled)} ${unit}`;
}

export function formatUnixWindow(window: [number, number] | null | undefined): string {
  if (!window) return "--";
  const [start, end] = window;
  return `${new Date(start * 1000).toISOString()} -> ${new Date(end * 1000).toISOString()}`;
}
