import { expect, test } from "@playwright/test";
import { load } from "./helpers";

test("standard scenario shows both visits with unique keys", async ({
  page,
}) => {
  const duplicateKeyWarnings: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes("same key"))
      duplicateKeyWarnings.push(message.text());
  });

  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const visits = page.locator(".job").filter({ hasText: "N-01" });
  await expect(visits).toHaveCount(2);
  await expect(
    visits.filter({ hasText: "Install · 120 min on-site" }),
  ).toHaveCount(1);
  await expect(
    visits.filter({ hasText: "Battery day · 60 min on-site" }),
  ).toHaveCount(1);
  await expect(
    visits.filter({ hasText: "Install · 120 min on-site" }),
  ).toBeVisible();
  await expect(
    visits.filter({ hasText: "Battery day · 60 min on-site" }),
  ).toBeVisible();
  expect(duplicateKeyWarnings).toEqual([]);

  await page.screenshot({
    path: "e2e/screenshots/standard-two-visit.png",
    fullPage: true,
  });
});

test("disruption bar summarizes storm impact and no-action cost", async ({
  page,
}) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const bar = page.getByTestId("disruption-bar");
  await expect(bar.locator(".disruption-summary strong")).toContainText(
    "visits affected",
  );
  await expect(bar).toContainText("This replay applies a modeled operational");
  await expect(bar.getByTestId("affected-visits")).toContainText("7");
  await expect(bar.getByTestId("deadlines-at-risk")).toContainText("7");
  await expect(bar.getByTestId("no-action-cost")).toContainText("$630.25");
  await expect(bar.getByText("Stub data")).toHaveCount(0);

  await page.screenshot({
    path: "e2e/screenshots/canvas-disruption.png",
    fullPage: true,
  });
});

test("cascade steps highlight affected visits", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const direct = page.getByTestId("cascade-direct");
  await expect(direct).toContainText("Visits using changed resources");
  await direct.click();
  await expect(direct).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("visit-S-02-B")).toHaveClass(/highlighted/);
  await expect(page.getByTestId("visit-S-02-I")).not.toHaveClass(/highlighted/);
  await page.getByRole("button", { name: "Clear highlight" }).click();
  await expect(page.getByTestId("visit-S-02-B")).not.toHaveClass(/highlighted/);
});

test("plan lanes order crews and show visit links and lost capacity", async ({
  page,
}) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const crewRows = page.locator(".calendar tbody tr");
  await expect(crewRows.nth(0)).toContainText("Crew IA");
  await expect(crewRows.nth(1)).toContainText("Crew IB");
  await expect(crewRows.nth(2)).toContainText("Crew BA");
  await expect(page.getByTestId("lost-capacity-IA-2018-06-14")).toBeVisible();
  await expect(page.getByTestId("visit-arc").first()).toBeAttached();

  await page.screenshot({
    path: "e2e/screenshots/canvas-lanes.png",
    fullPage: true,
  });
});

test("diff overlays show old positions and respect reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  await expect(page.locator(".moved-ghost").first()).toBeVisible();
  await expect(page.locator(".moved-visit").first()).toBeVisible();
  await expect(page.locator(".unchanged-visit").first()).toBeVisible();
  await expect(page.locator(".moved-visit").first()).toHaveCSS(
    "animation-name",
    "none",
  );

  await page.screenshot({
    path: "e2e/screenshots/canvas-diff.png",
    fullPage: true,
  });
});

test("options show modeled cost, customer impact, overtime, and lowest cost", async ({
  page,
}) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const options = page.getByTestId("option-list");
  await expect(options.locator("button[data-option-kind]")).toHaveCount(3);
  const rebalance = options.locator('[data-option-kind="rebalance"]');
  const temporary = options.locator('[data-option-kind="temporary_capacity"]');
  await expect(rebalance).toContainText("Lowest modeled cost");
  await expect(rebalance).toContainText("$353.83");
  await expect(temporary).toContainText("7 customers to reschedule");
  await expect(temporary).toContainText("$453.28");
  const overtime = options.locator('[data-option-kind="overtime"]');
  if (await overtime.count())
    await expect(overtime).toContainText("min overtime");

  await page.screenshot({
    path: "e2e/screenshots/canvas-options.png",
    fullPage: true,
  });
});

test("approve confirms the selected recovery option", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const panel = page.getByTestId("option-panel");
  await expect(panel).toContainText("Rebalance existing crews");
  await expect(panel).toContainText("$353.83");
  await page.getByTestId("approve-option").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("18 customers to reschedule");
  await dialog.getByRole("button", { name: "Confirm approval" }).click();
  await expect(page.getByTestId("approval-result")).toContainText(
    "Recovery approved for this analysis.",
  );
  await expect(page.getByTestId("approval-result")).not.toContainText(
    "Stub data.",
  );

  await page.screenshot({
    path: "e2e/screenshots/canvas-approve.png",
    fullPage: true,
  });
});

test("manipulate actions call the live evaluator", async ({ page }) => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Runs against the live API only.");
  const evaluations: { disruption: unknown[]; interventions: unknown[] }[] = [];
  const evaluationStatuses: number[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/evaluate"))
      evaluations.push(request.postDataJSON());
  });
  page.on("response", (response) => {
    if (response.url().endsWith("/api/recovery/evaluate"))
      evaluationStatuses.push(response.status());
  });
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const controls = page.getByTestId("evaluation-controls");
  const actions = [
    "Knock out Crew IB · Wed 13 Jun",
    "Add 120 min overtime",
    "Pin N-02 battery day",
    "Move N-02 battery day",
  ];
  for (const [index, name] of actions.entries()) {
    await controls.getByRole("button", { name }).click();
    await expect.poll(() => evaluations.length).toBe(index + 1);
    await expect.poll(() => evaluationStatuses.length).toBe(index + 1);
    expect(evaluationStatuses[index]).toBe(200);
    await expect(controls.locator(".evaluation-result")).toContainText(
      "Evaluate manual recovery changes",
    );
  }
  expect(evaluations[0].disruption).toHaveLength(4);
  expect(evaluations[1].interventions).toMatchObject([
    { kind: "extend_crew_day", extra_min: 120 },
  ]);
  expect(evaluations[2].interventions).toMatchObject([
    { kind: "pin_visit", job_id: "N-02-B" },
  ]);
  expect(evaluations[3].interventions).toMatchObject([
    { kind: "move_visit", job_id: "N-02-B" },
  ]);
});

test("live canvas loads recovery impact and options", async ({ page }) => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Runs against the live API only.");
  await load(page);
  await expect(page.getByText("Live API", { exact: true })).toBeVisible();
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");
  await expect(page.getByTestId("disruption-bar")).toContainText(
    "7 visits affected",
    { timeout: 60_000 },
  );
  await expect(
    page.getByTestId("option-list").locator("button[data-option-kind]"),
  ).not.toHaveCount(0);
  await page.locator('[data-option-kind="rebalance"]').click();
  await page.getByTestId("approve-option").click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Confirm approval" }).click();
  await expect(page.getByTestId("approval-result")).toContainText(
    "Recovery approved for this analysis.",
  );

  await page.screenshot({
    path: "e2e/screenshots/canvas-live.png",
    fullPage: true,
  });
});

test("option thumbnails compare crew load by day", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const cards = page.locator(".option-card");
  await expect(cards.first()).toBeVisible();
  await expect(cards.first().locator(".mini-lane")).toHaveCount(3);
  await expect(cards.first().locator(".mini-lane-day")).not.toHaveCount(0);
  await expect(
    cards.first().getByLabel("Crew load before and after"),
  ).toBeVisible();

  await page.screenshot({
    path: "e2e/screenshots/canvas-thumbnails.png",
    fullPage: true,
  });
});

test("economic drawer shows each line and its basis", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const breakdown = page.getByTestId("economic-breakdown");
  await breakdown.locator("summary").click();
  await expect(breakdown).toContainText("Lost modeled operating value");
  await expect(breakdown).toContainText(
    "Original minus option gross operating margin",
  );

  await page.screenshot({
    path: "e2e/screenshots/canvas-drawer.png",
    fullPage: true,
  });
});

test("assumptions edits are sent as economics overrides", async ({ page }) => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Runs against the live API only.");
  const requests: Record<string, unknown>[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/options"))
      requests.push(request.postDataJSON());
  });
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const assumptions = page.getByTestId("assumptions-panel");
  await assumptions.locator("summary").click();
  await assumptions
    .getByRole("spinbutton", { name: "hourly wage" })
    .fill("100");
  await assumptions.getByTestId("apply-economics").click();
  await expect
    .poll(() => requests.some((request) => request.economics_overrides))
    .toBe(true);
  expect(requests.at(-1)?.economics_overrides).toMatchObject({
    hourly_wage: 100,
  });
  await expect(assumptions).toContainText("Operator override");
});

test("map inset groups affected homes by cluster", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  const inset = page.getByTestId("affected-map-inset");
  await expect(inset).toContainText("Affected homes by cluster");
  const southCluster = inset.locator(".affected-cluster").filter({
    hasText: "7 affected homes",
  });
  await expect(southCluster).toContainText("S");
  await expect(southCluster).toContainText("7 affected homes");
  await expect(
    page.getByRole("button", { name: /Select S-02.*affected by disruption/ }),
  ).toBeVisible();
});

test("keyboard keys select options, approve, and knock out a crew-day", async ({
  page,
}) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");

  await page.keyboard.press("2");
  await expect(page.locator('[data-option-kind="rebalance"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.keyboard.press("a");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  const evaluations: unknown[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/evaluate"))
      evaluations.push(request.postDataJSON());
  });
  await page.keyboard.press("k");
  await expect.poll(() => evaluations.length).toBe(1);
});

test("dark canvas preserves readable recovery controls", async ({ page }) => {
  await load(page);
  await page
    .getByRole("combobox", { name: "Scenario" })
    .selectOption("standard");
  const lightBackground = await page
    .locator("body")
    .evaluate((body) => getComputedStyle(body).backgroundColor);

  await page.getByRole("button", { name: "Toggle dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkBackground = await page
    .locator("body")
    .evaluate((body) => getComputedStyle(body).backgroundColor);
  expect(darkBackground).not.toBe(lightBackground);
  await expect(page.getByTestId("disruption-bar")).toBeVisible();
  await expect(page.getByTestId("option-list")).toBeVisible();

  await page.screenshot({
    path: "e2e/screenshots/canvas-dark.png",
    fullPage: true,
  });
});
