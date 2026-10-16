module.exports = {
  apps: [
    {
      name: 'eskeylation-api',
      cwd: __dirname,
      script: 'uv',
      args: 'run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      kill_timeout: 10000,
      env: { ENVIRONMENT: 'prod', PYTHONUTF8: '1' },
    },
  ],
}
