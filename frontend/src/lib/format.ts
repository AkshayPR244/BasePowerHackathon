export const dateLabel = (date: string) =>
  new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
export function datesBetween(start: string, end: string) {
  const dates: string[] = [];
  for (let t = Date.parse(start); t <= Date.parse(end); t += 86400000)
    dates.push(new Date(t).toISOString().slice(0, 10));
  return dates;
}
export const money = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
