# Cold Email System - Django Application

## Obiectiv
Construiește o aplicație Django completă pentru cold email B2B outreach, integrată cu infrastructura existentă pe VPS Strato.

## Context infrastructură existentă
- **VPS**: Strato (IP: 85.215.69.83), Ubuntu 24.04, 6 vCPU, 24GB RAM, 400GB SSD
- **Stack existent**: Plesk, Docker, PostgreSQL 16, Redis, n8n la n8n.get-hub.io
- **Domeniu principal**: north-cleaning.de (NU trimite cold email de pe acest domeniu!)
- **Business**: North Cleaning Services GmbH — Gebäudereinigung Hamburg
- **Target audience**: Hausverwaltungen, Immobilienfirmen, Facility Management, Gewerbebetriebe în Hamburg

## Cerințe tehnice

### 1. Structură proiect Django
```
/opt/cold-email/
├── docker-compose.yml
├── .env
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── celery.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── campaigns/          # Campaign management
│   │   ├── models.py       # Campaign, EmailSequence, SequenceStep
│   │   ├── views.py        # Dashboard, campaign CRUD
│   │   ├── tasks.py        # Celery tasks pentru trimitere
│   │   ├── templates/
│   │   └── admin.py
│   ├── leads/              # Lead management
│   │   ├── models.py       # Lead, LeadList, LeadTag
│   │   ├── views.py        # Import CSV, manage leads
│   │   ├── importers.py    # DataforSEO import, CSV import
│   │   └── admin.py
│   ├── sending/            # Email sending engine
│   │   ├── models.py       # SMTPAccount, SendingSchedule, EmailLog
│   │   ├── sender.py       # SMTP rotation, sending logic
│   │   ├── warmup.py       # Warmup gradual logic
│   │   └── bounce.py       # Bounce handling
│   ├── tracking/           # Open/click tracking
│   │   ├── views.py        # Pixel endpoint, redirect endpoint
│   │   ├── models.py       # TrackingEvent
│   │   └── urls.py
│   ├── templates/          # Django templates (Tailwind CSS)
│   │   ├── base.html
│   │   ├── dashboard/
│   │   ├── campaigns/
│   │   ├── leads/
│   │   └── settings/
│   └── api/                # REST API pentru n8n webhooks
│       ├── views.py
│       ├── serializers.py
│       └── urls.py
```

### 2. Modele de date (PostgreSQL)

**Lead model:**
- business_name, email, phone, website, address, city, postal_code
- contact_person (opțional), position
- industry (hausverwaltung, immobilien, facility_management, gewerbe, other)
- source (dataforseo, manual, csv_import, website_form)
- status (new, contacted, replied, interested, not_interested, bounced, unsubscribed)
- tags (ManyToMany)
- gdpr_legal_basis = "legitimate_interest_b2b"  # Art. 6 Abs. 1 lit. f DSGVO
- unsubscribed, unsubscribed_at
- created_at, updated_at

**Campaign model:**
- name, description, status (draft, active, paused, completed)
- lead_list (ForeignKey)
- from_name, reply_to_email
- daily_send_limit (default 50)
- sending_window_start (default 08:00), sending_window_end (default 17:00)
- sending_days (default Mon-Fri)
- timezone = "Europe/Berlin"

**SequenceStep model:**
- campaign (ForeignKey)
- step_number (1, 2, 3...)
- subject_template (Jinja2)
- body_template (Jinja2 cu HTML)
- delay_days (câte zile după pasul anterior)
- send_only_if_no_reply = True

**EmailLog model:**
- lead, campaign, sequence_step
- smtp_account_used
- status (queued, sent, delivered, opened, clicked, replied, bounced, unsubscribed)
- sent_at, opened_at, clicked_at
- tracking_id (UUID pentru pixel tracking)
- message_id (SMTP Message-ID)

**SMTPAccount model:**
- email_address, smtp_host, smtp_port, smtp_username, smtp_password (encrypted)
- daily_limit (default 50), sent_today, last_reset_date
- warmup_mode (boolean), warmup_day (counter), warmup_start_date
- is_active, health_status
- domain (pentru rotație per domeniu)

### 3. Funcționalități core

**Email Sending Engine:**
- Rotație între mai multe SMTP accounts
- Rate limiting: max X emails/oră/cont, respectă daily limits
- Sending window: doar între 08:00-17:00 CET, luni-vineri
- Random delay între emailuri (30-120 secunde)
- Jinja2 template rendering cu personalizare: {{business_name}}, {{city}}, {{industry_text}}
- Automatic stop dacă lead-ul a răspuns (detectare reply pe IMAP)

**Warmup System:**
- Zi 1-3: 5 emailuri/zi
- Zi 4-7: 10 emailuri/zi
- Zi 8-14: 25 emailuri/zi
- Zi 15+: limita normală (50/zi)
- Track warmup progress per SMTP account

**Tracking:**
- Open tracking: endpoint `/t/open/<tracking_uuid>.png` → returnează 1x1 pixel transparent, loghează open
- Click tracking: endpoint `/t/click/<tracking_uuid>/<encoded_url>/` → redirect + log click
- Unsubscribe: endpoint `/unsubscribe/<tracking_uuid>/` → marchează lead ca unsubscribed, afișează confirmare

**Bounce Handling:**
- Parsare bounce emails via IMAP
- Auto-mark lead ca bounced
- După 3 bounce-uri pe un SMTP account → alertă

**DSGVO Compliance (OBLIGATORIU în fiecare email):**
- Header `List-Unsubscribe` cu link direct
- Footer cu Impressum complet North Cleaning Services GmbH
- Link dezabonare vizibil
- Menționare "berechtigtes Interesse gemäß Art. 6 Abs. 1 lit. f DSGVO"
- Doar adrese generice B2B (info@, kontakt@, office@, verwaltung@) — filtru automat care respinge adrese cu prenume.nume@

### 4. Dashboard (Django Templates + Tailwind)
- **Overview**: campanii active, emailuri trimise azi, open rate, reply rate
- **Campaigns**: listă, create/edit, start/pause, statistici per campanie
- **Leads**: import, filtrare, tag-uri, export, status overview
- **SMTP Accounts**: adăugare, warmup status, health check
- **Analytics**: grafice open/click/reply rate pe zi, per campanie
- **Logs**: toate emailurile trimise, cu status

### 5. Integrare n8n (via REST API + webhooks)
- `POST /api/leads/` — adaugă lead-uri din n8n (de la DataforSEO workflow)
- `POST /api/leads/import/` — import bulk
- `GET /api/campaigns/<id>/stats/` — statistici campanie
- `POST /api/webhooks/reply/` — n8n trimite notificare când detectează reply
- Webhook outgoing: trimite event la n8n când un lead deschide/click/reply

### 6. Email Templates preconfigurate (în germană)

**Secvență 1 — Inițial:**
Subject: "Gebäudereinigung für {{business_name}} — kostenlose Besichtigung"

**Secvență 2 — Follow-up (3 zile):**
Subject: "Kurze Rückfrage: Reinigungsangebot für {{business_name}}"

**Secvență 3 — Final (7 zile):**
Subject: "Letzte Frage: Dürfen wir Ihnen ein Angebot unterbreiten?"

Toate templateurile trebuie să fie profesionale, scurte, cu CTA clar, și footer DSGVO complet.

### 7. Docker Compose
```yaml
services:
  cold-email-app:
    build: ./app
    ports:
      - "8100:8000"
    env_file: .env
    depends_on:
      - cold-email-db
      - cold-email-redis
    volumes:
      - ./app:/app
    
  cold-email-db:
    image: postgres:16-alpine
    volumes:
      - cold_email_pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: cold_email
      POSTGRES_USER: cold_email_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  cold-email-redis:
    image: redis:7-alpine

  cold-email-celery:
    build: ./app
    command: celery -A config worker -l info -Q sending,tracking,warmup
    env_file: .env
    depends_on:
      - cold-email-db
      - cold-email-redis

  cold-email-beat:
    build: ./app
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    depends_on:
      - cold-email-db
      - cold-email-redis

volumes:
  cold_email_pgdata:
```

### 8. Domeniu secundar
- Configurează aplicația pentru a fi accesibilă la `mail.get-hub.io` sau `outreach.north-cleaning.de`
- IMPORTANT: Cold emailurile se trimit de pe un domeniu SECUNDAR (ex: `north-cleaning-services.de`) pentru a proteja reputația domeniului principal
- DNS records necesare: SPF, DKIM, DMARC pentru domeniul de trimitere

### 9. Securitate
- Django SECRET_KEY din .env
- SMTP passwords encrypted in DB (django-encrypted-model-fields)
- API authentication cu token-uri pentru n8n
- CSRF protection pe toate formularele
- Rate limiting pe API endpoints
- Admin panel securizat cu 2FA (django-otp)

### 10. Requirements.txt core
```
Django==5.0
djangorestframework==3.14
celery==5.3
redis==5.0
psycopg2-binary==2.9
django-celery-beat==2.5
Jinja2==3.1
django-encrypted-model-fields==0.6
python-decouple==3.8
gunicorn==21.2
imapclient==3.0
bleach==6.1
django-filter==23.5
whitenoise==6.5
requests==2.31
```

## Ordinea de implementare
1. Docker Compose + Django project setup + settings
2. Models (leads, campaigns, sending, tracking)
3. Sending engine cu SMTP rotation + rate limiting
4. Tracking endpoints (pixel, click, unsubscribe)
5. Celery tasks (send queue, warmup, bounce check)
6. Dashboard views + templates
7. REST API pentru n8n
8. Email templates în germană
9. Import leads din CSV
10. Testing + deployment

## Constrângeri
- Nu folosi niciun serviciu extern de email marketing (nu Brevo, nu Mailchimp)
- SMTP direct prin Mailgun, Amazon SES, sau SMTP propriu
- Totul self-hosted pe VPS-ul Strato
- Cod curat, comentat, production-ready
- Limba interfață: engleză (dashboard), limba emailuri: germană
