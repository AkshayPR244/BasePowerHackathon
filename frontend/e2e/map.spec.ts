import { test, expect } from "@playwright/test";
import { load, shot } from "./helpers";
test("map selection links to calendar and inspector", async ({ page }) => {
  await load(page);
  await page.getByRole("button", { name: "Select N-02, scheduled" }).click();
  await expect(page.locator(".job.selected")).toContainText("N-02");
  await expect(page.getByRole("complementary")).toContainText("N-02");
  await shot(page, "map");
});
