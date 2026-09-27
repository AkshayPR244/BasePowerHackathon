import { expect, test, type Page, type TestInfo } from "@playwright/test";

type Patch = { delayMs?: number; transform?: string };
// Transforms run in the page, so they travel as function source.
async function patchMocks(page: Page, patches: Record<string, Patch>) {
  await page.addInitScript((source) => {
    const parsed = JSON.parse(source) as Record<string, Patch>;
    (
      window as unknown as { __rolloutMockPatches: unknown }
    ).__rolloutMockPatches = Object.fromEntries(
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

async function openMockCanvas(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("live-results")).toBeVisible();
  await expect(page.locator(".option-chip").first()).toBeVisible();
}

const chip = (page: Page, kind: string) =>
  page.locator(`.option-chip[data-option-kind="${kind}"]`);

async function knockOutBaThursday(page: Page) {
  await page
    .getByTestId("crew-day-BA-2018-06-14")
    .locator(".crew-day-action")
    .click();
  await expect(page.getByTestId("live-headline")).toHaveText(
    "Crew BA loses Thu 14 Jun.",
  );
  await expect(page.getByTestId("live-results")).toBeVisible();
  await expect(page.getByTestId("previous-result")).toHaveCount(0);
}

test.describe("live canvas on recorded responses", () => {
  test.beforeEach(async () => {
    test.skip(process.env.CANVAS_LIVE === "1", "Uses recorded responses.");
  });

  test("live canvas is the default page and links to the workspace", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await openMockCanvas(page);
    await expect(page.getByTestId("live-headline")).toHaveText(
      "The current plan is ready to change.",
    );
    await expect(
      page.getByText("Synthetic plan", { exact: true }),
    ).toBeVisible();
    await expect(page.locator("body")).not.toContainText("storm");
    const optionChips = page.locator(".option-chip");
    await expect(optionChips.first()).toHaveCSS("min-height", "40px");
    const optionColors = await page
      .locator(".frontier-point")
      .evaluateAll((points) =>
        points.map((point) => ({
          kind: point.getAttribute("data-option-kind"),
          color: getComputedStyle(point.querySelector(".frontier-marker")!)
            .stroke,
        })),
      );
    expect(new Set(optionColors.map(({ kind }) => kind)).size).toBe(
      optionColors.length,
    );
    expect(
      new Set(optionColors.map(({ color }) => color).filter(Boolean)).size,
    ).toBe(optionColors.length);
    expect(
      (await page.locator(".frontier-svg").boundingBox())!.height,
    ).toBeGreaterThanOrEqual(300);
    const planBox = (await page.locator(".plan-figure").boundingBox())!;
    const frontierBox = (await page.locator(".frontier-figure").boundingBox())!;
    expect(frontierBox.y).toBeGreaterThanOrEqual(planBox.y + planBox.height);
    await page.screenshot({ path: "e2e/screenshots/live-canvas.png" });
    await expect(
      page.getByText("ERCOT 2018 hindsight value", { exact: true }),
    ).toBeVisible();
    await page.getByTestId("workspace-link").click();
    await expect(page).toHaveURL(/view=workspace.*scenario=standard/);
    await expect(page.getByTestId("shared-recovery-context")).toContainText(
      "same scenario and operational changes",
    );
    await expect(page.getByTestId("recovery-canvas")).toBeVisible();
    await expect(page.getByTestId("baseline-section")).toBeVisible();
    await page.getByTestId("live-canvas-link").click();
    await expect(page.getByTestId("live-recovery-canvas")).toBeVisible();
  });

  test("random trigger uses the supported recorded disruption", async ({
    page,
  }) => {
    await openMockCanvas(page);
    await page.getByRole("button", { name: "Random trigger" }).click();
    await expect(page.getByTestId("live-headline")).toHaveText(
      "Crew BA loses Thu 14 Jun.",
    );
    await expect(page.getByTestId("live-results")).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  });

  test("knocked-out crew-day shows ghosts and derived text", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await openMockCanvas(page);
    await knockOutBaThursday(page);
    const cell = page.getByTestId("lost-capacity-BA-2018-06-14");
    await expect(cell.locator(".lost-ghost")).toHaveCount(7);
    await expect(cell.getByTestId("ghost-S-02-B")).toBeVisible();
    await expect(page.getByTestId("live-subline")).toContainText(
      "7 visits displaced",
    );
    await expect(
      chip(page, "temporary_capacity").getByText("Lowest adjusted cost"),
    ).toBeVisible();
    await expect(page.locator("body")).not.toContainText("storm");
    await page.screenshot({ path: "e2e/screenshots/live-canvas-knockout.png" });
  });

  test("confirm dialog is modal and approves the option it opened for", async ({
    page,
  }) => {
    const approvals: { option: { option_id: string } }[] = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/api/recovery/approve"))
        approvals.push(request.postDataJSON());
    });
    await openMockCanvas(page);
    await chip(page, "rebalance").click();
    const approve = page.getByTestId("approve-option");
    await approve.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    expect(
      await page.evaluate(() =>
        document.querySelector("dialog")?.matches(":modal"),
      ),
    ).toBe(true);
    const focusInDialog = () =>
      page.evaluate(() => !!document.activeElement?.closest("dialog"));
    expect(await focusInDialog()).toBe(true);
    for (let n = 0; n < 4; n++) {
      await page.keyboard.press("Tab");
      expect(await focusInDialog()).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(approve).toBeFocused();

    await approve.click();
    await expect(dialog).toContainText("0 customers to reschedule");
    await dialog.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByTestId("approval-status")).toBeVisible();
    expect(approvals).toHaveLength(1);
    expect(approvals[0].option.option_id).toMatch(/^rebalance-/);
    await expect(approve).toBeDisabled();
  });

  test("approval resets on option change and ignores stale responses", async ({
    page,
  }) => {
    await patchMocks(page, { "/api/recovery/approve": { delayMs: 1500 } });
    let responded = false;
    page.on("response", (response) => {
      if (response.url().endsWith("/api/recovery/approve")) responded = true;
    });
    await openMockCanvas(page);
    await page.getByTestId("approve-option").click();
    await page.getByRole("button", { name: "Confirm approval" }).click();
    await chip(page, "rebalance").click();
    await expect.poll(() => responded, { timeout: 5000 }).toBe(true);
    await expect(page.getByTestId("approval-status")).toHaveCount(0);
    await expect(page.getByTestId("approve-option")).toBeEnabled();

    await page.getByTestId("approve-option").click();
    await page.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByTestId("approval-status")).toBeVisible();
    await chip(page, "no_action").click();
    await expect(page.getByTestId("approval-status")).toHaveCount(0);
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
          if (temporary) {
            temporary.status = "timeout_no_incumbent";
            temporary.result.objective = null;
            temporary.result.validation.checked = false;
          }
          return data;
        }`,
      },
    });
    await openMockCanvas(page);
    await knockOutBaThursday(page);
    await expect(chip(page, "temporary_capacity")).toHaveCount(0);
    await expect(
      page.locator('.frontier-point[data-option-kind="temporary_capacity"]'),
    ).toHaveCount(0);
    await expect(page.getByTestId("withheld-option")).toContainText(
      "Timed out (no plan found) · Not validated",
    );
    await chip(page, "rebalance").click();
    await expect(page.getByTestId("unproven-note")).toContainText(
      "Best found, not proven",
    );
    await expect(page.getByTestId("approve-option")).toBeEnabled();
  });

  test("theme follows the system setting and persists the operator choice", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await openMockCanvas(page);
    const background = () =>
      page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(await background()).toBe("rgb(23, 36, 39)");
    await knockOutBaThursday(page);
    await page.screenshot({ path: "e2e/screenshots/live-canvas-dark.png" });
    await page.getByTestId("theme-toggle").click();
    expect(await background()).toBe("rgb(237, 242, 239)");
    await page.reload();
    await expect(page.getByTestId("live-results")).toBeVisible();
    expect(await background()).toBe("rgb(237, 242, 239)");
  });
});

test.describe("live canvas against the live API", () => {
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
    expect(dimensions.documentHeight).toBeGreaterThanOrEqual(900);
    expect(dimensions.documentHeight).toBeLessThanOrEqual(1400);
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
    await expect(
      page.getByText("Synthetic plan", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("ERCOT 2018 hindsight value", { exact: true }),
    ).toBeVisible();
    await expect(page.locator(".cluster-key")).toContainText(
      "Houston service territories: N North · S South · W West",
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

    const optionPoints = page.locator(".frontier-point .frontier-marker");
    await expect(optionPoints.first()).toBeVisible();
    await expect(page.locator(".frontier-point text")).toHaveCount(0);
    await expect(page.locator(".option-chip")).toHaveCount(
      await optionPoints.count(),
    );
    const optionChips = page.locator(".option-chip");
    await expect(optionChips.first()).toHaveCSS("min-height", "40px");
    const optionColors = await page
      .locator(".frontier-point")
      .evaluateAll((points) =>
        points.map((point) => ({
          kind: point.getAttribute("data-option-kind"),
          color: getComputedStyle(point.querySelector(".frontier-marker")!)
            .stroke,
        })),
      );
    expect(new Set(optionColors.map(({ kind }) => kind)).size).toBe(
      optionColors.length,
    );
    expect(
      new Set(optionColors.map(({ color }) => color).filter(Boolean)).size,
    ).toBe(optionColors.length);
    for (let index = 0; index < (await optionChips.count()); index += 1) {
      await optionChips.nth(index).click();
      await expectVisibleCrewSkills(page);
    }
    if ((await optionPoints.count()) > 1) {
      await optionPoints.nth(1).click();
      await capture(page, info, "01-selected-option");
      await expect(page.getByTestId("selected-recovery")).toBeVisible();
    }

    await expect(page.locator(".crew-day").first()).toBeVisible();
    await capture(page, info, "02-by-crew");

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
    // Mon 4 Jun holds locked installs, so knock out the first unlocked day.
    await page
      .locator(
        '.crew-day[data-crew-id="IA"][data-date="2018-06-05"] .crew-day-action',
      )
      .click();
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
        '.crew-day[data-crew-id="IB"][data-date="2018-06-05"] .crew-day-action',
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
  });

  test("advanced workspace continues the primary disruption", async ({
    page,
  }, info) => {
    await openCanvas(page, info);
    await chooseTool(page, info, "knockout");
    await page
      .locator(
        '.crew-day[data-crew-id="IA"][data-date="2018-06-05"] .crew-day-action',
      )
      .click();
    await waitForRecovery(page, info, "shared-context-source");
    await page.getByTestId("workspace-link").click();

    await expect(page.getByTestId("shared-recovery-context")).toContainText(
      "Crew IA unavailable Tue 5 Jun",
    );
    await expect(page.getByTestId("disruption-description")).toContainText(
      "Crew IA unavailable Tue 5 Jun",
    );
    await expect(page.getByTestId("recovery-canvas")).toBeVisible();
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
    await chooseTool(page, info, "reschedule");
    await page.locator(".visit-mark > button").first().click();
    await expect(page.getByTestId("live-headline")).toContainText(
      "needs a new date",
    );
    await waitForRecovery(page, info, "03-home-rescheduled");
  });

  test("protect a home from movement", async ({ page }, info) => {
    await openCanvas(page, info);
    await chooseTool(page, info, "protect");
    const home = page.locator(".visit-mark > button").first();
    const homeId = (await home.locator("span").first().innerText()).trim();
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

  test("trace one home and reveal only its movement", async ({
    page,
  }, info) => {
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
});
