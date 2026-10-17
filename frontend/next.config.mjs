/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Produce a self-contained server bundle so the production Docker image only
  // needs the traced dependencies instead of the full node_modules tree.
  output: "standalone",

  // Server-side fetches to the FastAPI backend; keep this generous because a
  // cold Ollama model load can take a while.
  experimental: {
    serverActions: {
      bodySizeLimit: "4mb",
    },
  },

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "api.dicebear.com" },
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "github.com" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },

  // Shiki runs only in the server route handler, but Next still traverses the
  // module graph; stub Node's `fs`/`path` for the client bundle so it does not
  // try to polyfill them.
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false };
    }
    return config;
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
