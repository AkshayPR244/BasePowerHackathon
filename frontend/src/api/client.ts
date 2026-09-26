import createClient from "openapi-fetch";
import type { paths } from "./generated";
export const api = createClient<paths>({ baseUrl: "" });
export function unwrap<T>(response: { data?: T; error?: unknown }): T {
  if (response.error || response.data === undefined) {
    const error = response.error as
      { message?: string; detail?: unknown } | undefined;
    throw new Error(
      error?.message ??
        "The API could not complete this request. Check the connection and try again.",
    );
  }
  return response.data;
}
export const mockMode = import.meta.env.VITE_API_MODE !== "live";
