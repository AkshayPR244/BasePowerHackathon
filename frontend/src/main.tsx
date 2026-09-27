import React, { lazy, Suspense, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "./design/tokens.css";
import { mockMode } from "./api/client";
// Each view loads its own stylesheet, so the two layouts never share a page.
const params = new URLSearchParams(location.search);
const requestedView = params.get("view");
const View =
  requestedView === "workspace" ||
  (requestedView !== "primary" && params.has("scenario"))
    ? lazy(() =>
        import("./views/Workspace").then((m) => ({ default: m.Workspace })),
      )
    : lazy(() =>
        import("./views/LiveRecoveryCanvas").then((m) => ({
          default: m.LiveRecoveryCanvas,
        })),
      );

function DevelopmentServerStatus() {
  const [connected, setConnected] = useState(true);
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    let active = true;
    const check = async () => {
      try {
        const response = await fetch("/@vite/client", {
          method: "HEAD",
          cache: "no-store",
        });
        if (active) setConnected(response.ok);
      } catch {
        if (active) setConnected(false);
      }
    };
    const offline = () => setConnected(false);
    const online = () => void check();
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    const interval = window.setInterval(() => void check(), 4_000);
    void check();
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, []);
  if (connected) return null;
  return (
    <div className="development-server-alert" role="alert">
      Local SlackLine server disconnected. Restart Vite, then reload this page.
    </div>
  );
}

async function main() {
  if (mockMode) await (await import("./mocks/browser")).startMocks();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <DevelopmentServerStatus />
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
