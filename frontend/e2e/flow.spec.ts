import { test, expect } from "@playwright/test";
import { recovery, shot } from "./helpers";
test("load, remove crew-day, solve, compare, export and reset", async ({
  page,
}) => {
  await recovery(page);
  await page
    .getByRole("button", { name: "Compare plans", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Recovery changes" }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/recovery.*\.csv$/);
  await shot(page, "flow-export");
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(
    page.getByText("All 5 schedulable jobs meet their deadlines.", {
      exact: false,
    }),
  ).toBeVisible();
});
