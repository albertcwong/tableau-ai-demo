import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker
  output: 'standalone',
  
  // Rewrite /api/v1/* requests to backend
  // This allows both client-side and server-side code to use relative paths
  async rewrites() {
    const backendUrl = process.env.BACKEND_API_URL || 'http://backend:8000';
    
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
