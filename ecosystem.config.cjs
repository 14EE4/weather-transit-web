const path = require('path');

module.exports = {
  apps: [
    {
      name: 'weather-backend',
      cwd: __dirname,
      script: 'venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8100',
      interpreter: 'none',
      restart_delay: 2000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },
    {
      name: 'weather-frontend',
      script: 'serve',
      env: {
        PM2_SERVE_PATH: path.join(__dirname, 'Weather-Transport Recommendation UI/dist'),
        PM2_SERVE_PORT: 3100,
        PM2_SERVE_SPA: 'true',
        PM2_SERVE_HOMEPAGE: '/index.html',
      },
      restart_delay: 2000,
      autorestart: true,
    },
  ],
};
