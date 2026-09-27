import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "./design/tokens.css";
import { mockMode } from "./api/client";
// Each view loads its own stylesheet, so the two layouts never share a page.
const params = new URLSearchParams(location.search);
const View =
  params.get("view") === "workspace" || params.has("scenario")
    ? lazy(() =>
        import("./views/Workspace").then((m) => ({ default: m.Workspace })),
      )
    : lazy(() =>
        import("./views/LiveRecoveryCanvas").then((m) => ({
          default: m.LiveRecoveryCanvas,
        })),
      );
async function main() {
  if (mockMode) await (await import("./mocks/browser")).startMocks();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false, refetchOnWindowFocus: false },
            },
          })
        }
      >
        <Suspense fallback={null}>
          <View />
        </Suspense>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}
main().catch((error) => {
  document.getElementById("root")!.textContent =
    `Could not start the workspace: ${error.message}`;
});
