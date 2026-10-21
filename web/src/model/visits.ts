/** Requests per minute, readable: whole numbers, one decimal under ten. */
export function perMinute(rps: number): string {
  const value = rps * 60;
  return value < 10 ? value.toFixed(1) : String(Math.round(value));
}
