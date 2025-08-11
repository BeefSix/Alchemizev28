/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['localhost'],
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8001',
        pathname: '/static/**',
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8001/api/:path*',
      },
      {
        source: '/static/:path*',
        destination: 'http://localhost:8001/static/:path*',
      },
    ];
  },
  env: {
            API_BASE_URL: process.env.API_BASE_URL || 'http://localhost:8001',
  },
};

module.exports = nextConfig;
