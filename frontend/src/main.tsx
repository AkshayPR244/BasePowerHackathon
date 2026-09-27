import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "./design/tokens.css";
import "./design/live-canvas.css";
import { LiveRecoveryCanvas } from "./views/LiveRecoveryCanvas";
import { mockMode } from "./api/client";
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
        <LiveRecoveryCanvas />
      </QueryClientProvider>
    </React.StrictMode>,
  );
}
main().catch((error) => {
  document.getElementById("root")!.textContent =
    `Could not start the workspace: ${error.message}`;
});
