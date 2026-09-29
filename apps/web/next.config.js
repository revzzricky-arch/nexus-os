/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@nexus/shared", "three"],
  experimental: {
    // For scaffold, keep minimal
  },
  images: {
    remotePatterns: [],
  },
  // For Docker standalone
  output: process.env.DOCKER_BUILD ? "standalone" : undefined,
};

module.exports = nextConfig;
