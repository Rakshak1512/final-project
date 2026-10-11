# Smart Event Management System

A full-stack, production-oriented event management platform for colleges — event discovery, QR-code
registrations, faculty-managed certificates, notifications, and analytics — built with **FastAPI + Firebase Firestore**
on the backend and **React (Vite)** on the frontend.

---

## 1. Tech Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | React 18 (Vite), React Router DOM, Axios, Context API, Framer Motion, React Icons, Chart.js |
| Backend    | Python, FastAPI, Firebase Admin SDK, Google Cloud Firestore, Pydantic, JWT, Bcrypt, SMTP |
| Database   | Firebase Firestore (NoSQL Document Store) |

---

## 2. Project Structure

```
smart-event-management/
├── backend/
│   ├── app/
│   │   ├── core/                  # config, firebase, security, email, file & PDF/QR utils
│   │   ├── models/                # Domain models (User, Event, Registration, Certificate, ...)
│   │   ├── schemas/               # Pydantic request/response schemas
│   │   ├── db/                    # firestore_service (reusable Firestore queries & transactions)
│   │   ├── api/routes/            # auth, users, events, registrations, certificates, notifications, analytics
│   │   ├── dependencies.py        # get_current_user / require_role guards
│   │   └── main.py                # FastAPI app entrypoint
│   ├── uploads/                   # profile_pictures / event_posters / certificates / qrcodes
│   ├── migrate_mysql_to_firestore.py  # optional data migration tool
│   ├── requirements.txt
│   └── .env.example
├── database/
│   └── firebase_schema.md         # Firestore collections and document schema reference
├── firestore.rules                # Firestore security rules
├── frontend/
│   ├── src/
│   │   ├── api/                   # axios instance + service layer matching the backend contract
│   │   ├── components/            # layout, landing, dashboard, charts, ui, common
│   │   ├── context/               # AuthContext, ThemeContext
│   │   ├── pages/                 # landing, auth, student, faculty, shared
│   │   └── styles/global.css      # design system (glassmorphism, dark/light theme, utility classes)
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## 3. Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- A **Firebase Project** with **Firestore** enabled (or the local Firebase Firestore Emulator)
- An SMTP account (Gmail App Password, SendGrid, Mailgun, or Amazon SES) for real email delivery

---

## 4. Firebase Setup

### Option A: Firebase Service Account JSON (Recommended)
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Create a project and enable **Cloud Firestore** in Native mode.
3. Navigate to **Project Settings** -> **Service accounts**.
4. Click **Generate new private key** to download your JSON file.
5. Save this file inside `backend/` (e.g. `backend/firebase_credentials.json`).
6. Set `FIREBASE_CREDENTIALS_PATH=./firebase_credentials.json` in `backend/.env`.

### Option B: Environment Variables
Alternatively, set the individual variables in `backend/.env`:
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project-id.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

### Option C: Local Firestore Emulator (Offline / Local Dev)
If using the Firebase CLI emulator:
```
FIRESTORE_EMULATOR_HOST=localhost:8080
```

### Deploying Security Rules
Deploy `firestore.rules` with the Firebase CLI:
```bash
firebase deploy --only firestore:rules
```

---

## 5. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Firebase configuration and SMTP credentials
```

### Run the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API root: http://localhost:8000
- Interactive docs (Swagger UI): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

---

## 6. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

- App runs at http://localhost:5173
- The Vite dev server proxies `/api` and `/uploads` to `http://localhost:8000`.

### Build for production

```bash
npm run build
npm run preview
```

---

## 7. Migrating Existing MySQL Data (Optional)

If you have legacy data in a MySQL database, use the migration utility:

```bash
cd backend
python migrate_mysql_to_firestore.py --mysql-url="mysql+pymysql://root:password@localhost:3306/smart_event_management"
```

---

## 8. Security & Business Logic Notes

- **Password Security**: Passwords are hashed with **bcrypt** (via passlib) before storing in Firestore.
- **JWT Authentication**: Uses access and refresh tokens.
- **Role-Based Access Control**: `student`, `faculty`, and `admin` roles are strictly enforced at the FastAPI dependency layer.
- **Atomic Operations**: Event registrations and seat counters use Firestore atomic transactions to prevent overbooking and race conditions.
- **Certificates**: Access-controlled by student `registration_number`.


---

## 9. Demo / Test Users

The backend contains idempotent demo accounts for testing all four roles. They are created only when `SEED_TEST_USERS=true`.

| Role | Email | Password |
|---|---|---|
| Student | student@test.com | Student@123 |
| Faculty | faculty@test.com | Faculty@123 |
| Volunteer | volunteer@test.com | Volunteer@123 |
| Admin | admin@test.com | Admin@123 |

These are demo credentials only. Change or remove them before exposing a production system to real users.

Set `SEED_TEST_USERS=true` in `backend/.env` if you want demo test accounts provisioned on startup.

## 10. Email & AI Provider Configuration

### Email Authentication (Gmail SMTP exclusively)
EventSphere uses **Gmail SMTP (`smtplib`)** with `STARTTLS` on port 587 as the exclusive email delivery provider for:
- 6-digit registration OTP verification
- 6-digit password-reset OTP verification (no reset links)
- Institutional account approval & rejection alerts
- Event registration confirmation passes
- Certificate issuance notices

In `backend/.env`:
```env
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=smart.event.system2026@gmail.com
SMTP_PASSWORD=your_16_char_google_app_password
SMTP_FROM_NAME=EventSphere
SMTP_FROM_EMAIL=smart.event.system2026@gmail.com
SMTP_USE_TLS=True
```

### AI Chatbot (Google Gemini & OpenAI)
EventSphere features a database-grounded AI Assistant. In `backend/.env`:
```env
AI_PROVIDER=gemini
AI_MODEL=gemini-1.5-flash
GEMINI_API_KEY=your_gemini_api_key_here
# Alternative:
# OPENAI_API_KEY=your_openai_api_key_here
```
If an AI API key is not configured, EventSphere gracefully operates via its authoritative internal database query engine without breaking.

## 11. Running Locally

### Backend
```bash
cd smart-event-management-system/backend
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

### Frontend
```bash
cd smart-event-management-system/frontend
npm install
npm run dev
```
- App: http://localhost:5173

Never commit `.env`, Firebase service-account JSON, private keys, API keys, or JWT secrets to Git.
