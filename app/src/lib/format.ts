const tr = (digits: number) =>
  new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function num(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "–" : tr(digits).format(value);
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}%${tr(digits).format(Math.abs(value) * 100)}`;
}

export function date(iso: string): string {
  return new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(`${iso}T00:00:00`),
  );
}

export function tone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "var(--muted)";
  return value > 0 ? "var(--up)" : "var(--down)";
}
