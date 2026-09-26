import { test, expect } from "@playwright/test";
import { load, recovery, shot } from "./helpers";
test("stale result after a crew-day disruption", async ({ page }) => {
  await load(page);
  await page
    .getByRole("button", { name: "Remove crew-day", exact: true })
    .click();
  await expect(
    page.getByText("Previous result · changes not solved"),
  ).toBeVisible();
  await expect(page.locator(".result-area")).toHaveClass(/stale/);
  await expect(
    page.getByRole("button", { name: "Export JSON" }),
  ).toBeDisabled();
  await shot(page, "stale");
});
test("recovery compare and counterfactual", async ({ page }) => {
  await recovery(page);
  await expect(page.getByText("Late · 1 day", { exact: true })).toBeVisible();
  await shot(page, "recovery");
  await page
    .getByRole("button", { name: "Compare plans", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Recovery changes" }),
  ).toBeVisible();
  await shot(page, "compare");
  await page.locator(".job").filter({ hasText: "N-02" }).click();
  await page.getByRole("button", { name: "Require N-02 by deadline" }).click();
  await expect(
    page.getByText("Intervention infeasible", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add Crew C on first day" }).click();
  await expect(
    page.getByText("Intervention feasible", { exact: true }),
  ).toBeVisible();
  await shot(page, "counterfactual");
});
