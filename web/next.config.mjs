/** @type {import('next').NextConfig} */
const nextConfig = {
  // The app is client-rendered and talks to the agent API at runtime, so lint
  // config is kept out of the critical build path.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
