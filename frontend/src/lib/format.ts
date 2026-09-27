const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const months = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
// Fixed "Thu 14 Jun" format: Intl output varies by browser and locale.
export const dateLabel = (date: string) => {
  const day = new Date(`${date}T12:00:00Z`);
  return `${weekdays[day.getUTCDay()]} ${day.getUTCDate()} ${months[day.getUTCMonth()]}`;
};
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
