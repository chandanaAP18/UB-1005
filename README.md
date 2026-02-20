# MediSync AI Platform v3.0 🏥

Unified AI-powered healthcare intelligence platform with real authentication and comprehensive medical knowledge retrieval.

## 🆕 New Features in v3.0

### 🔐 Login System — **SECURE AUTHENTICATION**
- ✅ **Email/password** authentication with bcrypt password hashing
- ✅ **JWT** access tokens for secure session management
- ✅ User registration with role selection (Physician, Nurse, Admin, Researcher)
- ✅ Proper authentication endpoints with security validation

### 🧠 WellnessBot (Woebot & Wysa-inspired)
- CBT-based mental health support
- **Mood Tracker** — log mood, anxiety, energy, sleep daily
- **CBT Exercises** — thought records, 4-7-8 breathing timer, gratitude journal, 5-4-3-2-1 mindfulness
- **Crisis Resources** — US + international helplines, mental health apps
- Tab-based modular UI

### 🔍 MedRAG Agent — **ANSWERS ALL DISEASES**
- **Intelligent 4-stage retrieval system** answers questions about ANY disease or condition
- **50+ curated disease entries** with evidence-based guidelines
- **AI-powered fallback** generates structured clinical responses for all other queries
- **Clickable source links** — direct links to WHO, CDC, NICE, ADA, ACC/AHA, JAMA
- **Google Search integration** — click to search Google or PubMed for treatments
- Automatically categorizes queries (cancer, infection, mental health, etc.) and generates appropriate clinical guidance

### 💊 Prescription Management
- FHIR R4 standardization
- **Multi-format save**: PDF (HTML), JSON, TXT, DOCX
- File upload: JPG, PNG, PDF, TXT, DOCX

### 🩻 Scan Storage (**NEW**)
- Upload & store: **MRI, X-Ray, CT, Ultrasound, ECG, Echocardiogram, PET scans**
- Formats: JPEG, PNG, PDF, DICOM, TIFF
- Filter by type & patient name
- Image preview with fullscreen viewer
- Patient linking with ID

### ⚕️ Risk AI (Modular)
- 3 modules: **Single Patient**, **Batch Assessment**, **Urgent Queue**
- Explainable factors with clinical reasoning per parameter
- **Urgency triage** — flags CRITICAL/HIGH risk patients automatically
- Auto-populates Urgent Queue with immediate action links
- Google + PubMed treatment search links

### ⚠️ ADR Detection System (**NEW**)
- Real-time Adverse Drug Reaction detection using EHR data
- Drug interaction database (Warfarin+Aspirin, MAOIs+SSRIs, etc.)
- Severity classification: Critical / Moderate / Minor
- **Source links** with citations (BNF, FDA, Drugs.com, ACR)
- ADR event logging with patient tracking
- Google search integration for treatment management

### 📊 Enhanced Dashboard
- 6 live stats: Prescriptions, Sessions, Risk Checks, RAG Queries, Scans, ADR Events

### 📑 Reports
- 4 formats: **TXT, JSON, CSV, HTML**
- Includes ADR events & scan records
- Preview before download

## 🔑 Authentication Features

### ✅ Email/Password Authentication
- **Bcrypt password hashing** using `passlib[bcrypt]`
- Minimum 8-character password requirement
- Secure password verification

### ✅ JWT Token Management  
- **JWT access tokens** using `python-jose[cryptography]`
- 24-hour token expiration (configurable)
- Token stored in localStorage for session persistence

## 🧠 MedRAG — Universal Medical Knowledge

### How It Works
MedRAG uses a **4-stage intelligent retrieval system**:

1. **Direct Match** (50+ diseases): Instant lookup for common conditions
2. **Alias Matching**: Recognizes abbreviations (HTN → Hypertension, T2DM → Diabetes)
3. **Token Overlap**: Fuzzy matching for related queries
4. **AI-Generated Fallback**: Generates structured clinical responses for ANY disease not in database

### Example Queries That Work
- ✅ "Type 2 diabetes treatment" → Curated answer
- ✅ "HTN management" → Alias match → Hypertension
- ✅ "Kawasaki disease" → AI-generated structured response
- ✅ "Treatment for Addison's disease" → AI-generated response
- ✅ "Malaria prophylaxis" → Curated answer

**ALL queries receive evidence-based responses** with citations to WHO, CDC, NICE, NIH, etc.

---
MediSync AI v3.0 — Built for HealthTech Innovation Challenge 2026
**Secure Authentication ✓ | Universal Medical Knowledge ✓**
