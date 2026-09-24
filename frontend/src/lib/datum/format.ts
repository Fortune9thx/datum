export const VALUE_SCALE = 100;

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

export function formatUnixWindow(window: [number, number] | null | undefined): string {
  if (!window) return "--";
  const [start, end] = window;
  return `${new Date(start * 1000).toISOString()} -> ${new Date(end * 1000).toISOString()}`;
}
