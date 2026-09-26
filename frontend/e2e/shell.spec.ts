import { test, expect } from "@playwright/test";
import { load, shot } from "./helpers";
test("shell header calendar deferred inspector and dark", async ({ page }) => {
  await load(page);
  await expect(page.getByText("Synthetic data", { exact: true })).toBeVisible();
  await expect(page.getByText("Validated", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Crew calendar" }),
  ).toBeVisible();
  await expect(page.getByText("480 / 480 min")).toBeVisible();
  await shot(page, "shell");
  await shot(page, "header");
  await shot(page, "calendar");
  await page.locator(".deferred").filter({ hasText: "S-03" }).click();
  await expect(page.getByRole("complementary")).toContainText("panel_upgrade");
  await shot(page, "inspector");
  await page.getByRole("button", { name: "Toggle dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await shot(page, "shell-dark");
});
