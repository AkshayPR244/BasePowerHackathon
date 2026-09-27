import { expect, type Page } from "@playwright/test";
export async function load(page: Page) {
  await page.goto("/?scenario=tiny");
  await expect(
    page.getByText("All 5 schedulable jobs meet their deadlines.", {
      exact: false,
    }),
  ).toBeVisible();
}
export async function loadCanvas(page: Page) {
  await page.goto("/?view=workspace");
  await expect(page.getByTestId("impact-headline")).toContainText(
    "visits affected",
  );
  await expect(page.locator(".option-card").first()).toBeVisible();
}
export async function recovery(page: Page) {
  await load(page);
  await page
    .getByRole("button", { name: "Remove crew-day", exact: true })
    .click();
  await page.getByRole("button", { name: "Solve strict", exact: true }).click();
  await expect(page.getByText("Infeasible", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Find recovery", exact: true })
    .click();
  await expect(page.getByText("Recovery plan", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Compare plans", exact: true }),
  ).toBeEnabled();
}
export async function shot(page: Page, name: string) {
  await page.screenshot({
    path: `e2e/screenshots/${name}.png`,
    fullPage: true,
  });
}
