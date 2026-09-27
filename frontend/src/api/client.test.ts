import { expect, test } from "vitest";
import { unwrap } from "./client";

test("unwrap returns data", () => {
  expect(unwrap({ data: 3 })).toBe(3);
});

test("unwrap adds input issues to the error message", () => {
  expect(() =>
    unwrap({
      error: {
        code: "invalid_input",
        message: "The request has invalid input.",
        input_issues: [
          { code: "BAD_VALUE", message: "Date 2018-06-12 is frozen." },
          { code: "UNKNOWN_REFERENCE", message: "Crew C does not exist." },
        ],
      },
    }),
  ).toThrow(
    "The request has invalid input. Date 2018-06-12 is frozen. Crew C does not exist.",
  );
});

test("unwrap keeps the message when there are no input issues", () => {
  expect(() => unwrap({ error: { message: "Server error." } })).toThrow(
    /^Server error\.$/,
  );
});
