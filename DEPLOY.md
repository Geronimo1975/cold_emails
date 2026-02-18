# Cold Email — Deployment Guide (VPS Strato)

## 1. Copy project to VPS
```bash
scp -r /home/george/cold_emails/ root@85.215.69.83:/opt/cold-email/
```

## 2. Create .env on VPS
```bash
cd /opt/cold-email
cp .env.example .env
nano .env   # fill in all values
```

Generate FIELD_ENCRYPTION_KEY:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Start containers
```bash
docker compose up -d --build
```

## 4. Initialize database
```bash
docker compose exec cold-email-app python manage.py migrate
docker compose exec cold-email-app python manage.py createsuperuser
docker compose exec cold-email-app python manage.py collectstatic --noinput
```

## 5. Seed email templates
```bash
docker compose exec cold-email-app python manage.py seed_templates
```

## 6. Set up Celery Beat periodic tasks
Go to http://your-domain/admin/ → Periodic Tasks → add:

| Name                | Task                        | Schedule          |
|---------------------|-----------------------------|-------------------|
| Send scheduled      | sending.tasks.send_scheduled_emails | Every 5 min |
| Daily warmup        | sending.tasks.run_daily_warmup | Daily 06:00    |
| Check bounces       | sending.tasks.check_all_bounces | Every 2 hours |

## 7. Nginx/Plesk reverse proxy
Point `mail.get-hub.io` to `127.0.0.1:8100`

## 8. DNS records for sending domain (north-cleaning-services.de)
```
TXT  @    "v=spf1 include:mailgun.org ~all"
TXT  mail._domainkey   "v=DKIM1; k=rsa; p=<your_dkim_key>"
TXT  _dmarc  "v=DMARC1; p=quarantine; rua=mailto:dmarc@north-cleaning-services.de"
MX   @    10 mxb.mailgun.org
```

## 9. n8n integration
- Add API token from `.env` (API_TOKEN) to n8n HTTP Request headers: `Authorization: Token <your-token>`
- POST leads: `https://mail.get-hub.io/api/leads/import/`
- Reply webhook: `https://mail.get-hub.io/api/webhooks/reply/`
