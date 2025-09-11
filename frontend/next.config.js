/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  images: {
    domains: ['localhost'],
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8001',
        pathname: '/storage/**',
      },
    ],
  },
  async rewrites() {
    // Use localhost for development, Docker internal networking for containers
    const backendUrl = process.env.DOCKER_ENV 
      ? 'http://backend:8000'
      : 'http://localhost:8001';
    
    console.log('Next.js Proxy Backend URL:', backendUrl);
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
