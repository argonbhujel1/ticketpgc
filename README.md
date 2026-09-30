# Pathari Gold Cup 2026 — Ticket System

Dark Stadium × Gold × Red digital ticketing for Pathari / Pathrisanischare Gold Cup.

## Features

- Public: Home, Matches, Buy flow, Payment, Success, **full-size digital ticket**
- **PNG + PDF download** of stadium-style tickets with QR
- Verify ticket page
- Admin dashboard (matches, teams, classes, bookings, payments confirm)
- Gate scanner (manual code / ready for camera)
- Demo payment issues tickets instantly (QR method)

## Quick start

```bash
cd pathari-gold-cup   # or pgc folder
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
python run.py
```

Open: http://127.0.0.1:5000

**Admin:** http://127.0.0.1:5000/admin  
- Username: `admin`  
- Password: `ChangeMeNow123!`

**Scanner:** http://127.0.0.1:5000/scanner (login as admin first)

## Buy flow (test)

1. Home → Buy Ticket on a match  
2. Choose class + quantity → Continue  
3. Enter name + phone → Payment  
4. Select **QR / Demo Pay** → Proceed  
5. Success page shows **large ticket image** + Download PNG / PDF  

## Ticket design

Generated server-side (Pillow) as a wide stadium ticket:

- Left brand strip (Pathari Gold Cup)
- Center: teams, date, venue, class / gate / zone / price
- Right stub: Ticket ID, QR, SCAN AT GATE

Matches the professional horizontal ticket layout.

## Env (optional production)

```
SECRET_KEY=...
DATABASE_URL=postgresql://...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=...
```

## Note on payments

eSewa / ConnectIPS show **Currently unavailable** until you set in Admin → Settings:

- `payment_esewa_enabled` = `true`
- `payment_connectips_enabled` = `true`

Wire real gateway callbacks before going live. Demo QR path auto-issues tickets for testing.


## TextBee SMS + Email delivery

After admin **confirms payment**, the system:

1. Sends **SMS via TextBee** (`TEXTBEE_API_KEY`)
2. Always sends **email** with ticket **number + PNG image** attached
3. If SMS fails, email still goes out (marked that SMS failed)

```env
TEXTBEE_API_KEY=your_api_key_from_textbee_dashboard
TEXTBEE_BASE_URL=https://api.textbee.dev/api/v1
TEXTBEE_DEVICE_ID=   # optional

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=you@gmail.com
MAIL_PASSWORD=app-password
MAIL_DEFAULT_SENDER=you@gmail.com
SITE_URL=https://your-domain.com
```

Phone numbers are normalized to E.164 (e.g. `98xxxxxxxx` → `+97798xxxxxxxx`).

## Gate QR scanner

`/gate/login` → camera QR scan (html5-qrcode) + manual code entry.


## Deploy: Vercel + Aiven.io

1. Create **Aiven PostgreSQL** service → copy Connection URI (`?sslmode=require`).
2. Push this repo to GitHub.
3. Vercel → New Project → import repo.
4. **Root Directory**: folder that contains `run.py` (if nested, set it).
5. Environment variables (Production):

| Name | Value |
|------|--------|
| `DATABASE_URL` | Aiven URI |
| `SECRET_KEY` | long random |
| `FLASK_ENV` | `production` |
| `SITE_URL` | `https://your-app.vercel.app` |
| `TEXTBEE_API_KEY` | from textbee.dev |
| `MAIL_*` | SMTP for ticket PNG email |

6. Deploy. First request creates tables + seed admin/gate users.

**Note:** Uploaded files (QR, logos, proofs) on Vercel go to `/tmp` and are not permanent. For production media use object storage later.


## TextBee: "No enabled device found"

TextBee sends SMS **through your Android phone SIM**. Without a linked device, API returns 400.

**Webhook does NOT replace a device.** Webhooks only notify *you* when someone texts your phone.

### Setup device

1. Phone: Android + working SIM + internet  
2. Install TextBee APK from https://textbee.dev  
3. Dashboard → scan QR / link device → status **Online / Enabled**  
4. Copy **Device ID** from dashboard  
5. Vercel env:

```
TEXTBEE_API_KEY=...
TEXTBEE_DEVICE_ID=your_device_id_here
SITE_URL=https://your-app.vercel.app
```

6. Redeploy → Admin → Resend SMS + Email  

If you have **no Android phone**, use **email only** (MAIL_* env). SMS will stay skipped until a device is linked.
