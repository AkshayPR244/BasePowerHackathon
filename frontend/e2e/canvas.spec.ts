import { expect, test, type Page } from "@playwright/test";
import { loadCanvas } from "./helpers";

const lanes = (page: Page) => page.getByTestId("plan-lanes");
const rebalanceCard = (page: Page) =>
  page.locator('.option-card[data-option-kind="rebalance"]');
const noActionCard = (page: Page) =>
  page.locator('.option-card[data-option-kind="no_action"]');
// The temporary crew is the storm option that moves visits.
const temporaryCard = (page: Page) =>
  page.locator('.option-card[data-option-kind="temporary_capacity"]');

type Patch = { delayMs?: number; transform?: string };
// Transforms run in the page, so they travel as function source.
async function patchMocks(page: Page, patches: Record<string, Patch>) {
  await page.addInitScript((source) => {
    const parsed = JSON.parse(source) as Record<string, Patch>;
    (
      window as unknown as { __slackLineMockPatches: unknown }
    ).__slackLineMockPatches = Object.fromEntries(
      Object.entries(parsed).map(([path, patch]) => [
        path,
        {
          delayMs: patch.delayMs,
          transform: patch.transform
            ? (new Function(`return (${patch.transform})`)() as unknown)
            : undefined,
        },
      ]),
    );
  }, JSON.stringify(patches));
}

test("canvas first: the recovery canvas is the page", async ({ page }) => {
  await loadCanvas(page);
  await expect(page.getByTestId("recovery-canvas")).toBeVisible();
  const baseline = page.getByTestId("baseline-section");
  await expect(baseline).not.toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Solve strict" })).toHaveCount(
    0,
  );
  await expect(page.getByText("Test a crew absence")).toHaveCount(0);
  const height = await page.evaluate(
    () => document.documentElement.scrollHeight,
  );
  expect(height).toBeLessThan(3200);
  await page.screenshot({
    path: "e2e/screenshots/canvas-first.png",
    fullPage: true,
  });
  await baseline.locator("summary").click();
  await expect(
    page.getByRole("button", { name: "Solve strict" }),
  ).toBeVisible();
});

test("standard scenario shows both visits with unique keys", async ({
  page,
}) => {
  const duplicateKeyWarnings: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes("same key"))
      duplicateKeyWarnings.push(message.text());
  });
  await loadCanvas(page);

  const visits = lanes(page).locator("button.job").filter({ hasText: "N-01" });
  await expect(visits).toHaveCount(2);
  await expect(
    visits.filter({ hasText: "Install · 120 min on-site" }),
  ).toHaveCount(1);
  await expect(
    visits.filter({ hasText: "Battery day · 60 min on-site" }),
  ).toHaveCount(1);
  expect(duplicateKeyWarnings).toEqual([]);

  await page.screenshot({
    path: "e2e/screenshots/standard-two-visit.png",
    fullPage: true,
  });
});

test("disruption bar summarizes impact and no-action cost", async ({
  page,
}) => {
  await loadCanvas(page);

  const bar = page.getByTestId("disruption-bar");
  await expect(bar.getByTestId("impact-headline")).toContainText(
    "7 visits affected",
  );
  await expect(bar.getByTestId("affected-visits")).toContainText("7");
  await expect(bar.getByTestId("deadlines-at-risk")).toContainText("7");
  await expect(bar.getByTestId("no-action-cost")).toContainText("$630.25");
  await expect(bar.getByText("Stub data")).toHaveCount(0);

  await page.screenshot({
    path: "e2e/screenshots/canvas-disruption.png",
    fullPage: true,
  });
});

test("disruption bar matches the analyzed disruption", async ({ page }) => {
  await loadCanvas(page);
  const bar = page.getByTestId("disruption-bar");
  await expect(bar.getByTestId("disruption-description")).toHaveText(
    "Modeled disruption: all field crews unavailable Thu 14 Jun.",
  );
  await expect(bar).not.toContainText("storm");
  await expect(bar).not.toContainText("replay");
  for (const crew of ["IA", "IB", "BA"])
    await expect(
      page.getByTestId(`lost-capacity-${crew}-2018-06-14`),
    ).toBeVisible();
});

test("cascade steps highlight affected visits", async ({ page }) => {
  await loadCanvas(page);
  await temporaryCard(page).click();

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
  await loadCanvas(page);

  const crewRows = lanes(page).locator("tbody tr");
  await expect(crewRows.nth(0)).toContainText("Crew IA");
  await expect(crewRows.nth(1)).toContainText("Crew IB");
  await expect(crewRows.nth(2)).toContainText("Crew BA");
  const lost = page.getByTestId("lost-capacity-IA-2018-06-14");
  await expect(lost).toBeVisible();
  await expect(lost).toContainText("Unavailable · modeled disruption");
  await temporaryCard(page).click();
  await expect(page.getByTestId("visit-arc").first()).toBeAttached();

  await page.screenshot({
    path: "e2e/screenshots/canvas-lanes.png",
    fullPage: true,
  });
});

test("plan lanes open on the disruption week", async ({ page }) => {
  await loadCanvas(page);
  const scroller = lanes(page).locator(".table-scroll");
  const box = await scroller.boundingBox();
  const day = await lanes(page)
    .locator('thead th[data-date="2018-06-14"]')
    .boundingBox();
  const lost = await page
    .getByTestId("lost-capacity-BA-2018-06-14")
    .boundingBox();
  expect(box && day && lost).toBeTruthy();
  expect(day!.x).toBeGreaterThanOrEqual(box!.x);
  expect(day!.x + day!.width).toBeLessThanOrEqual(box!.x + box!.width + 1);
  expect(lost!.x + lost!.width).toBeLessThanOrEqual(box!.x + box!.width + 1);
  expect(
    await scroller.evaluate((element) => element.scrollLeft),
  ).toBeGreaterThan(0);
});

test("arcs link install and battery day only for moved, affected, or selected homes", async ({
  page,
}) => {
  await loadCanvas(page);
  await temporaryCard(page).click();
  const arcs = page.getByTestId("visit-arc");
  await expect(arcs.first()).toBeAttached();
  const temporaryArcs = await arcs.count();
  expect(temporaryArcs).toBeLessThan(45);

  await noActionCard(page).click();
  await expect(noActionCard(page)).toHaveAttribute("aria-pressed", "true");
  await expect(arcs).toHaveCount(0);
  await page.getByTestId("visit-N-01-I").click();
  await expect(arcs).toHaveCount(1);
});

test("diff overlays show old positions and respect reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await loadCanvas(page);
  await temporaryCard(page).click();

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

test("ghosts render in lost crew-day cells", async ({ page }) => {
  await loadCanvas(page);
  const stormCell = page.getByTestId("lost-capacity-BA-2018-06-14");
  await expect(stormCell.getByTestId("ghost-S-02-B")).toBeVisible();
  await expect(stormCell.locator(".moved-ghost")).toHaveCount(7);
  await expect(stormCell).not.toContainText("No visits planned");
});

test("options show adjusted cost, customer impact, overtime, and lowest cost", async ({
  page,
}) => {
  await loadCanvas(page);

  const options = page.getByTestId("option-list");
  const cards = options.locator("button[data-option-kind]");
  await expect(cards).toHaveCount(3);
  const rebalance = options.locator('[data-option-kind="rebalance"]');
  const temporary = options.locator('[data-option-kind="temporary_capacity"]');
  const noAction = options.locator('[data-option-kind="no_action"]');
  await expect(temporary).toContainText("Lowest adjusted cost");
  await expect(noAction.getByTestId("option-cost")).toContainText("$630.25");
  await expect(
    noAction.getByTestId("option-cost").locator("strong"),
  ).toHaveClass(/cost-positive/);
  await expect(noAction).not.toContainText("Lowest adjusted cost");
  await expect(rebalance).not.toContainText("Lowest adjusted cost");
  await expect(rebalance).toContainText("same plan as no action");
  await expect(temporary.getByTestId("option-customers")).toContainText("7");
  await expect(temporary.getByTestId("option-cost")).toContainText("$458.40");
  for (const card of await cards.all()) {
    await expect(card.locator(".option-details")).toContainText(
      /No overtime|\d+ min overtime/,
    );
    await expect(card.getByTestId("option-validation")).toContainText(
      "Validator checked",
    );
  }

  await page.screenshot({
    path: "e2e/screenshots/canvas-options.png",
    fullPage: true,
  });
});

test("no lowest-cost option still renders every card with deadlines", async ({
  page,
}) => {
  await patchMocks(page, {
    "/api/recovery/options": {
      transform: `(data) => {
        data.no_action.lowest_modeled_cost = false;
        for (const option of data.options) option.lowest_modeled_cost = false;
        return data;
      }`,
    },
  });
  await loadCanvas(page);
  await expect(page.getByTestId("no-lowest-note")).toBeVisible();
  await expect(page.getByText("Lowest adjusted cost")).toHaveCount(0);
  const cards = page.locator(".option-card");
  await expect(cards).toHaveCount(3);
  for (const card of await cards.all()) {
    await expect(card.getByTestId("option-cost")).toBeVisible();
    await expect(card.getByTestId("option-deadlines")).toContainText(
      "Deadlines missed",
    );
    await expect(card.getByTestId("option-customers")).toContainText(
      "Customers to reschedule",
    );
  }
  await expect(noActionCard(page)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("option-panel")).toContainText(
    "Keep original crews",
  );
});

test("approve confirms the selected recovery option", async ({ page }) => {
  await loadCanvas(page);

  await temporaryCard(page).click();
  const panel = page.getByTestId("option-panel");
  await expect(panel).toContainText("Add temporary crew TEMP-BA on Fri 15 Jun");
  await expect(panel).toContainText("$458.40");
  await page.getByTestId("approve-option").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("7 customers to reschedule");
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

test("approval resets on option change and ignores stale responses", async ({
  page,
}) => {
  await loadCanvas(page);
  await page.getByTestId("approve-option").click();
  await page.getByRole("button", { name: "Confirm approval" }).click();
  await expect(page.getByTestId("approval-result")).toBeVisible();
  await rebalanceCard(page).click();
  await expect(page.getByTestId("approval-result")).toHaveCount(0);
  await noActionCard(page).click();
  await expect(page.getByTestId("approval-result")).toHaveCount(0);
  await expect(page.getByTestId("approve-option")).toBeEnabled();
});

test("slow approval response does not land on another option", async ({
  page,
}) => {
  await patchMocks(page, { "/api/recovery/approve": { delayMs: 1500 } });
  let responded = false;
  page.on("response", (response) => {
    if (response.url().endsWith("/api/recovery/approve")) responded = true;
  });
  await loadCanvas(page);
  await page.getByTestId("approve-option").click();
  await page.getByRole("button", { name: "Confirm approval" }).click();
  await rebalanceCard(page).click();
  await expect.poll(() => responded, { timeout: 5000 }).toBe(true);
  await expect(page.getByTestId("approval-result")).toHaveCount(0);
  await noActionCard(page).click();
  await expect(page.getByTestId("approval-result")).toHaveCount(0);
});

test("confirm dialog is modal and approves the option it opened for", async ({
  page,
}) => {
  const approvals: { option: { option_id: string } }[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/approve"))
      approvals.push(request.postDataJSON());
  });
  await loadCanvas(page);
  const approve = page.getByTestId("approve-option");
  await approve.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const focusInDialog = () =>
    page.evaluate(() => !!document.activeElement?.closest("dialog"));
  expect(await focusInDialog()).toBe(true);
  for (let n = 0; n < 4; n++) {
    await page.keyboard.press("Tab");
    expect(await focusInDialog()).toBe(true);
  }
  await page.keyboard.press("2");
  await expect(temporaryCard(page)).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(approve).toBeFocused();

  await page.keyboard.press("a");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("2");
  await dialog.getByRole("button", { name: "Confirm approval" }).click();
  await expect(page.getByTestId("approval-result")).toBeVisible();
  expect(approvals).toHaveLength(1);
  expect(approvals[0].option.option_id).toMatch(/^temporary_capacity-/);
});

test("invalid and unproven options are labeled and never drawn or approved", async ({
  page,
}) => {
  await patchMocks(page, {
    "/api/recovery/options": {
      transform: `(data) => {
        const [rebalance, temporary] = data.options;
        rebalance.status = "feasible";
        rebalance.proven_optimal = false;
        temporary.result.validation.valid = false;
        temporary.result.validation.issues = [{ code: "capacity", message: "Crew TEMP-BA exceeds capacity." }];
        data.no_action.status = "timeout_no_incumbent";
        return data;
      }`,
    },
  });
  await loadCanvas(page);
  await expect(rebalanceCard(page).getByTestId("option-status")).toContainText(
    "Best found, not proven",
  );
  await rebalanceCard(page).click();
  await expect(page.getByTestId("approve-option")).toBeEnabled();

  const temporary = page.locator(
    '.option-card[data-option-kind="temporary_capacity"]',
  );
  await expect(temporary.getByTestId("option-validation")).toContainText(
    "Validator found 1 violation",
  );
  await temporary.click();
  await expect(page.getByTestId("approve-option")).toBeDisabled();
  await expect(lanes(page).locator(".calendar-notice")).toContainText(
    "no validated plan to draw",
  );
  await expect(lanes(page).locator("button.job")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /Select S-02, no valid plan/ }),
  ).toBeVisible();

  await noActionCard(page).click();
  await expect(noActionCard(page).getByTestId("option-status")).toContainText(
    "Timed out (no plan found)",
  );
  await expect(page.getByTestId("approve-option")).toBeDisabled();
});

test("scenario round trip resets the canvas and never shows another scenario's plan", async ({
  page,
}) => {
  await loadCanvas(page);
  await noActionCard(page).click();
  await page.getByTestId("cascade-direct").click();
  const scenario = page.getByRole("combobox", { name: "Scenario" });
  await scenario.selectOption("tiny");
  await expect(page.getByTestId("no-recovery-case")).toBeVisible();
  await expect(page.getByTestId("recovery-canvas")).toHaveCount(0);
  await expect(
    page.getByText("All 5 schedulable jobs meet their deadlines.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.locator('[data-testid^="visit-S-02-"]')).toHaveCount(0);
  await expect(page.getByTestId("visit-N-01")).toBeVisible();

  const solves: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/plans")
      solves.push(request.postDataJSON().scenario_id);
  });
  await scenario.selectOption("standard");
  await expect(page.getByTestId("impact-headline")).toBeVisible();
  await expect(temporaryCard(page)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("cascade-direct")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await page.getByTestId("baseline-section").locator("summary").click();
  await expect(page.getByText("Strict plan", { exact: true })).toBeVisible();
  expect(solves).toEqual(["standard"]);
});

test("assumption edits reject empty or negative values and recover from errors", async ({
  page,
}) => {
  await loadCanvas(page);
  const assumptions = page.getByTestId("assumptions-panel");
  await assumptions.locator("summary").click();
  const wage = assumptions.getByRole("spinbutton", { name: "hourly wage" });
  const apply = assumptions.getByTestId("apply-economics");
  await wage.fill("");
  await expect(apply).toBeDisabled();
  await wage.fill("-5");
  await expect(apply).toBeDisabled();
  await wage.fill("100");
  await expect(apply).toBeEnabled();
  await apply.click();
  await expect(assumptions.getByTestId("economics-error")).toContainText(
    "no recorded response",
  );
  await expect(page.locator(".option-card")).toHaveCount(3);
  await assumptions.getByTestId("reset-economics").click();
  await expect(assumptions.getByTestId("economics-error")).toHaveCount(0);
  await expect(page.locator(".option-card")).toHaveCount(3);
  await expect(wage).toHaveValue("28.33");
});

test("manipulate actions call the live evaluator", async ({ page }) => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Runs against the live API only.");
  const evaluations: {
    disruption: unknown[];
    interventions: unknown[];
    revision: number;
  }[] = [];
  const evaluationStatuses: number[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/evaluate"))
      evaluations.push(request.postDataJSON());
  });
  page.on("response", (response) => {
    if (response.url().endsWith("/api/recovery/evaluate"))
      evaluationStatuses.push(response.status());
  });
  await page.goto("/?view=workspace");
  await expect(page.getByTestId("impact-headline")).toBeVisible({
    timeout: 60_000,
  });

  const controls = page.getByTestId("evaluation-controls");
  for (const [index, id] of [
    "knockout-crew-day",
    "overtime-crew-day",
    "pin-visit",
    "move-visit",
  ].entries()) {
    // After the storm only battery days remain, so only Crew BA can take a move.
    if (id === "move-visit")
      await controls.getByLabel("Crew").selectOption("BA");
    await controls.getByTestId(id).click();
    await expect.poll(() => evaluationStatuses.length).toBe(index + 1);
    expect(evaluationStatuses[index]).toBe(200);
    await expect(controls.locator(".evaluation-result")).toBeVisible();
  }
  expect(evaluations[0].disruption).toHaveLength(4);
  expect(evaluations[1].interventions).toMatchObject([
    { kind: "extend_crew_day", extra_min: 120 },
  ]);
  expect(evaluations[2].interventions).toMatchObject([{ kind: "pin_visit" }]);
  expect(evaluations[3].interventions).toMatchObject([{ kind: "move_visit" }]);
});

test("live canvas loads recovery impact and options", async ({ page }) => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Runs against the live API only.");
  await page.goto("/?view=workspace");
  await expect(page.getByText("Live API", { exact: true })).toBeVisible();
  await expect(page.getByTestId("disruption-bar")).toContainText(
    "7 visits affected",
    { timeout: 60_000 },
  );
  await expect(
    page.getByTestId("option-list").locator("button[data-option-kind]"),
  ).not.toHaveCount(0);
  await rebalanceCard(page).click();
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
  await loadCanvas(page);

  const cards = page.locator(".option-card");
  await expect(cards.first()).toBeVisible();
  await expect(cards.first().locator(".mini-lane")).toHaveCount(3);
  await expect(cards.first().locator(".mini-lane-day")).not.toHaveCount(0);
  await expect(
    cards.first().getByLabel("Crew load before and after"),
  ).toBeVisible();
  await expect(cards.first()).toContainText("Crew workload before and after");
  await expect(cards.first().getByLabel("Workload legend")).toContainText(
    "Before",
  );
  await expect(cards.first().getByLabel("Workload legend")).toContainText(
    "After",
  );

  await page.screenshot({
    path: "e2e/screenshots/canvas-thumbnails.png",
    fullPage: true,
  });
});

test("economic drawer shows each line and its basis", async ({ page }) => {
  await loadCanvas(page);

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
  await page.goto("/?view=workspace");
  await expect(page.getByTestId("impact-headline")).toBeVisible({
    timeout: 60_000,
  });

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
  await loadCanvas(page);

  await expect(
    page.getByRole("heading", { name: "Houston service clusters" }),
  ).toBeVisible();
  await expect(page.locator(".houston-center")).toBeVisible();
  await expect(page.locator(".map-compass")).toBeVisible();
  const inset = page.getByTestId("affected-map-inset");
  await expect(inset).toContainText("Affected homes by cluster");
  const southCluster = inset.locator(".affected-cluster").filter({
    hasText: "7 affected homes",
  });
  await expect(southCluster).toContainText("S");
  await expect(
    page.getByRole("button", { name: /Select S-02.*affected by disruption/ }),
  ).toBeVisible();
});

test("keyboard keys select options, approve, and knock out a crew-day", async ({
  page,
}) => {
  await loadCanvas(page);

  await page.keyboard.press("1");
  await expect(noActionCard(page)).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("2");
  await expect(rebalanceCard(page)).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("a");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  const evaluations: {
    disruption: { crew_id: string; date: string }[];
    interventions: unknown[];
  }[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/recovery/evaluate"))
      evaluations.push(request.postDataJSON());
  });
  await page.keyboard.press("k");
  await expect.poll(() => evaluations.length).toBe(1);
  expect(evaluations[0].disruption).toHaveLength(4);
  expect(evaluations[0].disruption.at(-1)).toMatchObject({
    kind: "remove_crew_day",
    crew_id: "IA",
    date: "2018-06-15",
  });
  expect(evaluations[0].interventions).toEqual([]);
  await expect(
    page.getByTestId("evaluation-controls").locator(".evaluation-result"),
  ).toContainText("Validator checked");
});

test("dark canvas preserves readable recovery controls", async ({ page }) => {
  await loadCanvas(page);
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
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("theme follows the system setting until the operator picks one", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await loadCanvas(page);
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.+/);
  await expect(
    page.getByRole("button", { name: "Toggle dark mode" }),
  ).toHaveText("Light");
  const background = await page
    .locator("body")
    .evaluate((body) => getComputedStyle(body).backgroundColor);
  expect(background).toBe("rgb(23, 36, 39)");
});
