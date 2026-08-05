import type { NextConfig } from "next";

const API = process.env.BHASHASETU_API ?? "http://127.0.0.1:8000";

// Deployment builds set this. Free hosting gives you one process on one port,
// so in production the FastAPI app serves the exported frontend itself and the
// browser sees a single origin — no proxy and no CORS, for the same reason the
// dev proxy exists below.
const staticExport = process.env.BHASHASETU_STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(staticExport
    ? {
        // Pre-rendered HTML + JS, so the deployed image needs no Node runtime.
        // Every page here is a client component, so nothing is lost by it.
        output: "export" as const,
        // The image optimiser is a server feature; the artwork is inline SVG.
        images: { unoptimized: true },
      }
    : {
        // Proxy the API through Next in dev so the browser sees one origin.
        // That keeps the httpOnly device cookie first-party — a cross-origin
        // cookie would be dropped by default in most browsers, and the
        // anonymous identity (spec §5) would silently stop persisting.
        //
        // `rewrites` is unsupported under `output: "export"`, and unnecessary
        // there: one server is already serving both halves.
        async rewrites() {
          return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
        },
      }),
};

export default nextConfig;
