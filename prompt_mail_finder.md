**Sarcina ta:**

Creează două scripturi Python complete și funcționale pentru extragerea emailurilor de pe LinkedIn și website-uri folosind Apollo.io, urmate de validarea lor pentru eliminarea bounce mails.

**Script 1: Extragere emailuri cu Apollo.io**

Dezvoltă un script Python care:
- Se conectează la API-ul Apollo.io pentru extragerea emailurilor din:
  - Profile LinkedIn (utilizatori individuali și angajați din companii)
  - Website-uri (liste de URL-uri furnizate)
  - Directoare business sau liste publice
- Acceptă ca input:
  - Lista de URL-uri LinkedIn (profile sau pagini de companii)
  - Lista de URL-uri website-uri
  - Fișier CSV sau JSON cu datele de input
- Extrage pentru fiecare email găsit: adresa email, nume complet, companie, poziție/job title, sursă (LinkedIn/website/director)
- Implementează rate limiting automat pentru a respecta limitele API Apollo.io
- Include retry logic cu exponential backoff pentru request-uri eșuate
- Salvează rezultatele în CSV cu coloanele: email, nume, companie, pozitie, sursa, data_extragere
- Generează logging detaliat în console și fișier (apollo_scraping.log) pentru monitorizare
- Gestionează autentificarea prin API key configurat prin variabilă de environment (APOLLO_API_KEY)
- Afișează progress bar pentru procesarea batch-urilor

**Script 2: Validare emailuri prin SMTP direct**

Creează un script Python independent care:
- Citește fișierul CSV generat de primul script
- Implementează validare multiplă pentru fiecare email:
  - **Validare sintaxă**: verifică format valid prin regex și librăria email-validator
  - **Validare DNS**: verifică existența domeniului și prezența MX records
  - **Validare SMTP soft**: realizează conexiune la serverul de mail și verifică existența mailbox-ului fără trimitere efectivă de email (SMTP VRFY/RCPT TO commands)
  - **Detectare disposable emails**: identifică servicii temporare de email (10minutemail, tempmail, etc.)
- Clasifică fiecare email în: VALID, INVALID, RISKY (risc de bounce), DISPOSABLE, UNKNOWN
- Generează raport CSV de output cu coloane: email, status_validare, motiv_invalidare, mx_records_found, smtp_response, timestamp_verificare
- Include toate datele originale din CSV-ul de input plus statusul de validare
- Folosește procesare asincronă (asyncio) pentru verificări SMTP paralele și rapide
- Afișează progress bar cu statistici în timp real (total procesate, valid, invalid, risc)
- Permite configurare prin parametri:
  - Batch size (câte emailuri să proceseze simultan)
  - Timeout pentru conexiuni SMTP (default 10 secunde)
  - Skip disposable check (opțional)
- Salvează emailurile invalide separat în failed_emails.csv pentru review

**Cerințe tehnice obligatorii:**

Pentru ambele scripturi asigură-te că includ:
- Fișier requirements.txt cu toate dependențele și versiuni exacte (apollo-python-sdk, email-validator, dnspython, aiosmtplib, tqdm, python-dotenv)
- Configurare prin fișier .env pentru API keys și setări (exemplu inclus în .env.example)
- Gestionare completă de excepții cu mesaje clare și utile pentru debugging
- Docstrings detaliate pentru toate funcțiile și clasele
- Comentarii inline pentru logica complexă
- Funcții modulare reutilizabile
- Type hints pentru parametri și return values

**Livrabile finale:**

Furnizează în format ready-to-use:
1. **apollo_scraper.py** - Script complet pentru extragere cu Apollo.io, cu comentarii explicative
2. **email_validator.py** - Script complet pentru validare SMTP directă, cu comentarii explicative
3. **requirements.txt** - Lista tuturor library-urilor necesare cu versiuni fixate
4. **README.md** - Documentație completă cu:
   - Cerințe de sistem (Python 3.8+)
   - Pași de instalare (pip install -r requirements.txt)
   - Configurare API key Apollo.io
   - Exemple de rulare pentru ambele scripturi
   - Parametri disponibili și opțiuni
   - Troubleshooting pentru probleme comune
5. **.env.example** - Template pentru fișierul .env cu variabilele necesare (APOLLO_API_KEY, SMTP_TIMEOUT, BATCH_SIZE)
6. **Exemplu de fișier input** - CSV sample cu structura așteptată pentru input-ul scriptului de extragere

Asigură-te că scripturile:
- Pot fi rulate independent unul de celălalt
- Sunt optimizate pentru procesarea a sute sau mii de emailuri (batch processing eficient)
- Au error handling robust pentru cazuri edge (conexiuni întrerupte, rate limits, timeout-uri)
- Pot fi oprite și reluate (checkpoint recovery pentru procesări lungi)
- Generează rapoarte clare și actionable pentru utilizator