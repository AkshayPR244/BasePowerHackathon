import { expect, test, type Page, type TestInfo } from "@playwright/test";

test.beforeEach(async () => {
  test.skip(process.env.CANVAS_LIVE !== "1", "Uses the real recovery API.");
});

async function openCanvas(page: Page, info: TestInfo) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await expect(page.getByTestId("live-recovery-canvas")).toBeVisible();
  await expect(page.getByTestId("live-results")).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, info, "00-baseline");
}

async function capture(page: Page, info: TestInfo, name: string) {
  const dimensions = await page.evaluate(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
    documentWidth: document.documentElement.scrollWidth,
    documentHeight: document.documentElement.scrollHeight,
  }));
  expect(dimensions.width).toBe(1440);
  expect(dimensions.height).toBe(900);
  expect(dimensions.documentWidth).toBeLessThanOrEqual(1440);
  expect(dimensions.documentHeight).toBeLessThanOrEqual(900);
  await page.screenshot({ path: info.outputPath(`${name}.png`) });
}

async function chooseTool(page: Page, info: TestInfo, tool: string) {
  await page.getByTestId(`tool-${tool}`).click();
  await expect(page.getByTestId(`tool-${tool}`)).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await capture(page, info, `01-tool-${tool}`);
}

async function waitForRecovery(page: Page, info: TestInfo, name: string) {
  await expect(page.getByTestId("live-results")).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByTestId("working-state")).toHaveCount(0);
  await expect(page.getByTestId("previous-result")).toHaveCount(0);
  await capture(page, info, name);
}

async function expectVisibleCrewSkills(page: Page) {
  const mismatches = await page
    .locator(".crew-row-fragment")
    .evaluateAll((rows) =>
      rows.flatMap((row) => {
        const role = row
          .querySelector(".crew-label small")
          ?.textContent?.trim();
        return [...row.querySelectorAll(".visit-mark")]
          .filter((visit) => {
            const expectedRole = visit.classList.contains("visit-install")
              ? "Install crew"
              : "Battery crew";
            return role !== "Temporary crew" && role !== expectedRole;
          })
          .map((visit) => ({ role, visit: visit.textContent?.trim() }));
      }),
    );
  expect(mismatches).toEqual([]);
}

test("baseline, linked options, plan views, and approval", async ({
  page,
}, info) => {
  await openCanvas(page, info);
  await expect(page.getByText("Synthetic plan", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Costs are modeled", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".cluster-key")).toContainText(
    "N North, S South, W West",
  );
  const triggerMeanings = [
    ["knockout", "Remove this crew-day's capacity."],
    ["halfday", "Keep half of its available minutes."],
    ["long", "Subtract this visit's duration from its crew-day."],
    ["reschedule", "Set this home's visits to start next business day."],
    ["protect", "Pin its visits to their current crews and days."],
    ["trace", "Compare its current and recovered battery day."],
  ];
  for (const [tool, meaning] of triggerMeanings) {
    await expect(page.getByTestId(`tool-${tool}`)).toContainText(meaning);
  }

  const optionPoints = page.locator(".frontier-point circle");
  await expect(optionPoints.first()).toBeVisible();
  await expect(page.locator(".frontier-point text")).toHaveCount(0);
  await expect(page.locator(".option-chip")).toHaveCount(
    await optionPoints.count(),
  );
  const optionChips = page.locator(".option-chip");
  for (let index = 0; index < (await optionChips.count()); index += 1) {
    await optionChips.nth(index).click();
    await expectVisibleCrewSkills(page);
  }
  if ((await optionPoints.count()) > 1) {
    await optionPoints.nth(1).click();
    await capture(page, info, "01-selected-option");
    await expect(page.getByTestId("selected-recovery")).toBeVisible();
  }

  await page.getByRole("button", { name: "By home" }).click();
  await expect(page.locator(".home-row")).toHaveCount(45);
  await capture(page, info, "02-by-home");
  await page.getByRole("button", { name: "By crew" }).click();
  await expect(page.locator(".crew-day").first()).toBeVisible();
  await capture(page, info, "03-by-crew");

  await page.getByTestId("approve-option").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await capture(page, info, "04-approve-confirmation");
  await page.getByRole("button", { name: "Confirm approval" }).click();
  await expect(page.getByTestId("approval-status")).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, info, "05-approved");
});

test("knock out a crew-day from the plan", async ({ page }, info) => {
  await openCanvas(page, info);
  await chooseTool(page, info, "knockout");
  await page.route("**/api/recovery/options", async (route) => {
    if (route.request().postDataJSON()?.revision === 1) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    await route.continue();
  });
  const evaluation = page.waitForResponse(
    (response) =>
      response.url().includes("/api/recovery/evaluate") &&
      response.request().method() === "POST",
  );
  await page.locator(".crew-day-action:not(:disabled)").first().click();
  await expect(page.getByTestId("previous-result")).toBeVisible();
  await expect(page.getByTestId("plan-figure")).toBeVisible();
  await expect(page.getByTestId("live-subline")).toContainText(
    "Reassigning its visits",
  );
  await expect(page.getByTestId("approve-option")).toBeDisabled();
  await expect(page.getByTestId("selected-recovery")).toContainText(
    "Previous result. Approval is paused",
  );
  await capture(page, info, "01-previous-result-while-solving");
  const evaluated = await evaluation;
  expect(evaluated.ok()).toBeTruthy();
  expect(await evaluated.json()).toMatchObject({ kind: "custom" });
  expect(evaluated.request().postDataJSON()).toMatchObject({
    scenario_id: "standard",
    revision: 1,
    interventions: [],
  });
  await expect(page.getByTestId("live-headline")).toContainText("loses");
  await waitForRecovery(page, info, "02-knockout-applied");
  await expect(
    page.locator('.option-chip[data-option-kind="custom"]'),
  ).toBeVisible();
  await expect(page.locator(".trace-overlay-arrival path")).toHaveCount(1);
  await expect(page.locator(".move-origin-anchor")).toHaveCount(1);
  await expect(page.locator(".visit-old-mark")).toHaveCount(0);
  const movedVisit = page.locator(".visit-moved > button").first();
  const movedShade = await movedVisit.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  const originalShade = await page
    .locator(".visit-install:not(.visit-moved) > button")
    .first()
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(movedShade).not.toBe(originalShade);
  await page.locator(".trigger-rail").hover();
  await page.waitForTimeout(1500);
  await expect(page.locator(".trace-overlay-arrival path")).toHaveCount(0);
  await expect(movedVisit).toBeVisible();
  expect(
    await movedVisit.evaluate(
      (element) => getComputedStyle(element).backgroundColor,
    ),
  ).toBe(movedShade);

  const previousSlots = await page
    .locator(".visit-mark > button")
    .evaluateAll((buttons) =>
      Object.fromEntries(
        buttons.map((button) => {
          const cell = button.closest(".crew-day");
          return [
            button.dataset.newKey,
            `${cell?.getAttribute("data-crew-id")}|${cell?.getAttribute("data-date")}`,
          ];
        }),
      ),
    );
  await page
    .locator(
      '.crew-day[data-crew-id="IB"][data-date="2018-06-04"] .crew-day-action',
    )
    .click();
  await expect(page.getByTestId("live-headline")).toContainText(
    "Crew IB loses",
  );
  await waitForRecovery(page, info, "03-second-change-applied");
  const origin = await page
    .locator(".move-origin-anchor")
    .evaluate((anchor) => ({
      key: anchor.getAttribute("data-old-key"),
      slot: `${anchor.parentElement?.getAttribute("data-crew-id")}|${anchor.parentElement?.getAttribute("data-date")}`,
    }));
  expect(previousSlots[origin.key ?? ""]).toBe(origin.slot);
  await page.getByRole("button", { name: "By home" }).click();
  await expect(page.locator(".visit-key")).toContainText(
    "Previous plan battery day",
  );
  await expect(page.locator(".home-row").first()).toHaveAttribute(
    "aria-label",
    /previous plan battery day/,
  );
  await capture(page, info, "04-second-change-by-home");
});

test("cut a crew-day to half capacity", async ({ page }, info) => {
  await openCanvas(page, info);
  await chooseTool(page, info, "halfday");
  await page.locator(".crew-day-action:not(:disabled)").nth(1).click();
  await expect(page.getByTestId("live-headline")).toContainText("half day");
  await waitForRecovery(page, info, "02-half-day-applied");
});

test("mark a visit as running long", async ({ page }, info) => {
  await openCanvas(page, info);
  await chooseTool(page, info, "long");
  await page.locator(".visit-mark > button").first().click();
  await expect(page.getByTestId("live-headline")).toContainText("runs long");
  await waitForRecovery(page, info, "02-running-long-applied");
});

test("reschedule a home from the plan", async ({ page }, info) => {
  await openCanvas(page, info);
  await page.getByRole("button", { name: "By home" }).click();
  await capture(page, info, "01-by-home");
  await chooseTool(page, info, "reschedule");
  await page.locator(".home-row").first().click();
  await expect(page.getByTestId("live-headline")).toContainText(
    "needs a new date",
  );
  await waitForRecovery(page, info, "03-home-rescheduled");
});

test("protect a home from movement", async ({ page }, info) => {
  await openCanvas(page, info);
  await page.getByRole("button", { name: "By home" }).click();
  await capture(page, info, "01-by-home");
  await chooseTool(page, info, "protect");
  const home = page.locator(".home-row").first();
  const homeId = (await home.locator("strong").innerText()).trim();
  const evaluation = page.waitForResponse(
    (response) =>
      response.url().includes("/api/recovery/evaluate") &&
      response.request().method() === "POST",
  );
  await home.click();
  const evaluated = await evaluation;
  expect(evaluated.ok()).toBeTruthy();
  expect(evaluated.request().postDataJSON().interventions).toContainEqual(
    expect.objectContaining({ kind: "pin_visit" }),
  );
  await expect(page.getByTestId("live-headline")).toContainText(
    `${homeId} is protected`,
  );
  await waitForRecovery(page, info, "03-home-protected");
});

test("trace one home and reveal only its movement", async ({ page }, info) => {
  await openCanvas(page, info);
  const movableVisit = page
    .locator('.visit-mark button[data-state="scheduled"]')
    .first();
  const crewDay = movableVisit.locator(
    "xpath=ancestor::div[contains(@class,'crew-day')]",
  );
  await chooseTool(page, info, "knockout");
  await crewDay.locator(".crew-day-action").click();
  await waitForRecovery(page, info, "02-triggered-plan");
  const movedVisit = page.locator(".visit-moved > button").first();
  await expect(movedVisit).toBeVisible();
  await chooseTool(page, info, "trace");
  await movedVisit.hover();
  await expect(page.locator(".trace-overlay path")).toHaveCount(1);
  await capture(page, info, "03-one-move-traced");
  await movedVisit.click();
  await expect(page.getByText(/Tracing home/)).toBeVisible();
  await capture(page, info, "04-home-traced");
});

test("random trigger re-solves and reset restores the baseline", async ({
  page,
}, info) => {
  await openCanvas(page, info);
  await page.getByTestId("random-trigger").click();
  await expect(page.getByTestId("live-headline")).not.toContainText(
    "ready to change",
  );
  await waitForRecovery(page, info, "01-random-trigger");
  await page.getByTestId("reset-plan").click();
  await expect(page.getByTestId("live-headline")).toContainText(
    "current plan is restored",
  );
  await waitForRecovery(page, info, "02-reset-baseline");
});
