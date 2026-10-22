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
    {
      name: 'eskeylation-media-worker',
      cwd: __dirname,
      script: 'uv',
      args: 'run --no-sync celery -A app.workers.celery_app:celery_app worker --beat --schedule .local/media-worker/beat --loglevel INFO --concurrency 1 --max-tasks-per-child 25 --max-memory-per-child 262144 --without-gossip --without-mingle',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      kill_timeout: 165000,
      restart_delay: 5000,
      env: { ENVIRONMENT: 'prod', PYTHONUTF8: '1' },
    },
  ],
}
