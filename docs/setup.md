# GitHub App Setup

1. Create a GitHub App at https://github.com/settings/apps/new
2. Set webhook URL to `https://your-host/webhook`
3. Generate a private key and download it
4. Set permissions: Pull requests (read/write), Contents (read), Checks (write)
5. Subscribe to events: Pull request
6. Install the app on your repositories
7. Configure environment variables (see `.env.example`)
8. Deploy via Docker: `docker compose up`
