import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { narrativeFor, narratives } from "./index";
import { ScenarioBriefing } from "../components/ScenarioBriefing";
import { presetFor } from "../scenario-presets";

describe("frontend-only scenario briefings", () => {
  it("has one complete report per operational preset", () => {
    const presets = import.meta.glob("../scenario-presets/*.json", {
      eager: true,
      import: "default",
    });
    expect(Object.keys(presets)).toHaveLength(10);
    expect(Object.keys(narratives)).toHaveLength(10);
    for (const [id, report] of Object.entries(narratives)) {
      expect(report.scenario_id).toBe(id);
      expect(presetFor(id)?.scenario_id).toBe(id);
      expect(report.what_to_watch.length).toBeGreaterThan(0);
      for (const value of Object.values(report))
        expect(value.length).toBeGreaterThan(0);
    }
  });
  it("renders no invented story when metadata is missing", () => {
    expect(
      renderToStaticMarkup(
        <ScenarioBriefing
          report={narrativeFor("unknown")}
          primaryActive={false}
          onApply={() => {}}
          disabled={false}
          hasDisruption={false}
        />,
      ),
    ).toBe("");
  });
  it("separates baseline and primary-trigger copy and always shows the truth label", () => {
    const report = narratives.crew_out_recoverable;
    for (const active of [false, true]) {
      const html = renderToStaticMarkup(
        <ScenarioBriefing
          report={report}
          primaryActive={active}
          onApply={() => {}}
          disabled={false}
          hasDisruption
        />,
      );
      expect(html).toContain("Scenario briefing");
      expect(html).toContain(report.truth_label);
      expect(html).toContain(active ? report.trigger : report.situation);
      expect(html).not.toContain(active ? report.situation : report.trigger);
      expect(html).toContain('<details open="">');
    }
  });
});
