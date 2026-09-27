import createClient from "openapi-fetch";
import type { paths } from "./generated";
export const api = createClient<paths>({ baseUrl: "" });
export function unwrap<T>(response: { data?: T; error?: unknown }): T {
  if (response.error || response.data === undefined) {
    const error = response.error as
      { message?: string; input_issues?: { message?: string }[] } | undefined;
    const issues = (error?.input_issues ?? [])
      .map((issue) => issue.message?.trim())
      .filter(Boolean);
    const message =
      error?.message ??
      "The API could not complete this request. Check the connection and try again.";
    throw new Error(issues.length ? `${message} ${issues.join(" ")}` : message);
  }
  return response.data;
}
export const mockMode = import.meta.env.VITE_API_MODE !== "live";
