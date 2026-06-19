import { StrictMode, Suspense, lazy, Component, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "@/App";
import "@/index.css";
import "@/i18n"; // initialiser i18next før React renderer

const Devtools = import.meta.env.DEV
  ? lazy(async () => {
      const m = await import("@tanstack/react-query-devtools");
      return { default: m.ReactQueryDevtools };
    })
  : null;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Mangler #root i index.html");
}

class RootErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[RootErrorBoundary] app krasjet:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-xlent-surface p-8 text-center text-xlent-ink">
          <h1 className="text-lg font-semibold">Applikasjonen kunne ikke lastes</h1>
          <p className="max-w-md text-sm text-xlent-muted">
            {this.state.error.message || "En uventet feil oppstod."}
          </p>
          <button
            className="rounded bg-xlent-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={() => window.location.reload()}
          >
            Last inn på nytt
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

window.addEventListener("vite:preloadError", (event) => {
  event.preventDefault();
  window.location.reload();
});

createRoot(rootElement).render(
  <StrictMode>
    <RootErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        {Devtools ? (
          <Suspense fallback={null}>
            <Devtools initialIsOpen={false} />
          </Suspense>
        ) : null}
      </QueryClientProvider>
    </RootErrorBoundary>
  </StrictMode>,
);
