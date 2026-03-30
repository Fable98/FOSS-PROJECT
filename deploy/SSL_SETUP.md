# Nginx + SSL Setup

This project now supports production deployment behind Nginx with Let's Encrypt.

## 1. Prepare DNS

Point these records to your server's public IP:

- `example.com`
- `www.example.com`

## 2. Prepare env file

```bash
cp .env.production.example .env.production
```

Update at least:

- `DOMAIN`
- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `ALLOWED_ORIGINS`

Keep `REACT_APP_API_URL=` empty so the frontend uses the same domain and Nginx proxies `/api`.

## 3. Start the stack once on HTTP

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build nginx frontend backend db redis
```

Nginx will start in HTTP-only mode until the certificate exists.

## 4. Issue the certificate

Replace `example.com` with your real domain:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml --profile tools run --rm certbot certonly --webroot -w /var/www/certbot -d example.com -d www.example.com --email you@example.com --agree-tos --no-eff-email
```

## 5. Reload Nginx

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart nginx
```

## 6. Open the app

- `https://example.com`
- `https://example.com/docs`

## Renewal

Run this periodically with cron:

```bash
docker compose --env-file /path/to/.env.production -f /path/to/docker-compose.prod.yml --profile tools run --rm certbot renew
docker compose --env-file /path/to/.env.production -f /path/to/docker-compose.prod.yml restart nginx
```

## Notes

- Ports `80` and `443` must be open in your cloud firewall.
- If the certificate command fails, DNS is usually the cause.
- Backend and frontend are no longer exposed directly in production; only Nginx is public.
