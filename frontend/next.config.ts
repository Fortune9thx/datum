import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async redirects() {
    // The board and ticket moved under /app when the app shell landed.
    return [
      { source: "/board", destination: "/app", permanent: true },
      { source: "/e/:id", destination: "/app/e/:id", permanent: true },
    ];
  },
};

export default nextConfig;
