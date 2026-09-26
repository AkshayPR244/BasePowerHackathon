import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Status, statusLabels } from "./status";
import type { Schema } from "../api/types";
test("every state has a readable label and a shape", () => {
  for (const state of Object.keys(statusLabels) as Schema["JobState"][]) {
    const html = renderToStaticMarkup(<Status state={state} />);
    expect(html).toContain(statusLabels[state]);
    expect(html).toContain("<svg");
  }
});
