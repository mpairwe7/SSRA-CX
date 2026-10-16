/**
 * Africa/Juba (`UTC+02:00`) Fiscal Calendar & Deadline Helper (`packages/ui/src/juba-calendar.ts` — Section 2 & 10.4).
 *
 * Uses Temporal-compatible plain date representations so frontend deadline displays match
 * `libs/ssra_core/src/ssra_core/clock.py` 100%.
 */

export const JUBA_TIMEZONE = "Africa/Juba" as const;

export interface JubaPlainDate {
  readonly year: number;
  readonly month: number; // 1..12
  readonly day: number; // 1..31
}

export function getSouthSudanFiscalYear(date: JubaPlainDate): string {
  if (date.month >= 7) {
    return `${date.year}/${date.year + 1}`;
  }
  return `${date.year - 1}/${date.year}`;
}

export function computeJubaMonthlyFilingDeadline(
  taxPeriodYear: number,
  taxPeriodMonth: number,
  deadlineDayOfFollowingMonth = 15,
): {
  readonly dueDateIso: string;
  readonly timezone: "Africa/Juba";
  readonly utcOffset: "+02:00";
} {
  const dueYear = taxPeriodMonth === 12 ? taxPeriodYear + 1 : taxPeriodYear;
  const dueMonth = taxPeriodMonth === 12 ? 1 : taxPeriodMonth + 1;

  const candidate = new Date(Date.UTC(dueYear, dueMonth - 1, deadlineDayOfFollowingMonth));
  // Roll Saturday (6) or Sunday (0) forward to Monday
  while (candidate.getUTCDay() === 0 || candidate.getUTCDay() === 6) {
    candidate.setUTCDate(candidate.getUTCDate() + 1);
  }

  const y = candidate.getUTCFullYear();
  const m = String(candidate.getUTCMonth() + 1).padStart(2, "0");
  const d = String(candidate.getUTCDate()).padStart(2, "0");
  return {
    dueDateIso: `${y}-${m}-${d}T23:59:59+02:00`,
    timezone: JUBA_TIMEZONE,
    utcOffset: "+02:00",
  };
}
