import type { NextConfig } from "next";

const API = process.env.BHASHASETU_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Proxy the API through Next in dev so the browser sees one origin. That keeps
  // the httpOnly device cookie first-party — a cross-origin cookie would be
  // dropped by default in most browsers, and the anonymous identity (spec §5)
  // would silently stop persisting.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
