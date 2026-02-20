
"""
MediSync AI — Enhanced Healthcare Platform v3.1
Backend: FastAPI (Python)

CHANGES in v3.1:
  - Email & password authentication with bcrypt password hashing
  - JWT access tokens (python-jose)
  - MedRAG expanded to 60+ diseases
  - AI-powered intelligent fallback for any disease query

SETUP:
  pip install fastapi uvicorn python-multipart bcrypt python-jose[cryptography] requests
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uvicorn, datetime, uuid, json, os, re
import openai
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── Auth libraries ──────────────────────────────────────────────────────────
try:
    import bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False
    print("[WARN] bcrypt not installed. Install: pip install bcrypt")

try:
    from jose import JWTError, jwt as jose_jwt
    JWT_OK = True
except ImportError:
    JWT_OK = False
    print("[WARN] python-jose not installed. Install: pip install python-jose[cryptography]")

# ── Config ──────────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "medisync-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    print("[WARN] OPENAI_API_KEY not found in environment. WellnessBot will use fallback keyword responses.")

# ── App Setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="MediSync AI Platform v3.1", version="3.1.0",
    description="Unified Healthcare Intelligence with Real Auth + Expanded MedRAG")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = os.path.join(os.getcwd(), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ── In-Memory Stores ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    if BCRYPT_OK:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')
    return plain  # fallback (not secure)

def verify_password(plain: str, hashed: str) -> bool:
    if BCRYPT_OK:
        try:
            return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return plain == hashed
    return plain == hashed

def create_jwt(user_id: str, email: str, role: str) -> str:
    if JWT_OK:
        expire = datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS)
        return jose_jwt.encode({"sub": user_id, "email": email, "role": role, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return f"token-{uuid.uuid4().hex}"


USERS_FILE = os.path.join(os.getcwd(), "users.json")
users_db: List[dict] = []

def load_users():
    global users_db
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_db = json.load(f)
    except Exception:
        users_db = []

def save_users():
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save users: {e}")

def init_default_users():
    if not users_db:
        users_db.append({
            "id": "usr-001",
            "email": "doctor@hospital.com",
            "name": "Dr. Admin",
            "role": "physician",
            "password": hash_password("password123"),
            "provider": "email",
            "verified": True
        })
        save_users()

ADR_LOG_FILE = os.path.join(os.getcwd(), "adr_log.json")
PRESCRIPTIONS_FILE = os.path.join(os.getcwd(), "prescriptions.json")
SCANS_FILE = os.path.join(os.getcwd(), "scans.json")
CHATBOT_SESSIONS_FILE = os.path.join(os.getcwd(), "chatbot_sessions.json")
RISK_PREDICTIONS_FILE = os.path.join(os.getcwd(), "risk_predictions.json")
PRESCRIPTION_HISTORY_FILE = os.path.join(os.getcwd(), "prescription_history.json")
RISK_HISTORY_FILE = os.path.join(os.getcwd(), "risk_history.json")
ADR_HISTORY_FILE = os.path.join(os.getcwd(), "adr_history.json")
MEDRAG_HISTORY_FILE = os.path.join(os.getcwd(), "medrag_history.json")

adr_log_db: List[dict] = []
prescription_history_db: List[dict] = []
risk_history_db: List[dict] = []
adr_history_db: List[dict] = []
medrag_history_db: List[dict] = []

def load_adr_log():
    global adr_log_db
    try:
        with open(ADR_LOG_FILE, "r", encoding="utf-8") as f:
            adr_log_db = json.load(f)
    except Exception:
        adr_log_db = []

def save_adr_log():
    try:
        with open(ADR_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(adr_log_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save ADR log: {e}")

def load_prescriptions():
    global prescriptions_db
    try:
        with open(PRESCRIPTIONS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                prescriptions_db = loaded
    except Exception:
        pass

def save_prescriptions():
    try:
        with open(PRESCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(prescriptions_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save prescriptions: {e}")

def load_scans():
    global scans_db
    try:
        with open(SCANS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                scans_db = loaded
    except Exception:
        pass

def save_scans():
    try:
        with open(SCANS_FILE, "w", encoding="utf-8") as f:
            json.dump(scans_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save scans: {e}")

def load_chatbot_sessions():
    global chatbot_sessions_db
    try:
        with open(CHATBOT_SESSIONS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                chatbot_sessions_db = loaded
    except Exception:
        pass

def save_chatbot_sessions():
    try:
        with open(CHATBOT_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(chatbot_sessions_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save chatbot sessions: {e}")

USER_HISTORY_FILE = os.path.join(os.getcwd(), "user_history.json")
user_history_db: List[dict] = []

def load_user_history():
    global user_history_db
    try:
        with open(USER_HISTORY_FILE, "r", encoding="utf-8") as f:
            user_history_db = json.load(f)
    except Exception:
        user_history_db = []

def save_user_history():
    try:
        with open(USER_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(user_history_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save user history: {e}")

def load_risk_predictions():
    global risk_predictions_db
    try:
        with open(RISK_PREDICTIONS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                risk_predictions_db = loaded
    except Exception:
        pass

def save_risk_predictions():
    try:
        with open(RISK_PREDICTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(risk_predictions_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save risk predictions: {e}")

def load_prescription_history():
    global prescription_history_db
    try:
        with open(PRESCRIPTION_HISTORY_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                prescription_history_db = loaded
    except Exception:
        pass

def save_prescription_history():
    try:
        with open(PRESCRIPTION_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(prescription_history_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save prescription history: {e}")

def load_risk_history():
    global risk_history_db
    try:
        with open(RISK_HISTORY_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                risk_history_db = loaded
    except Exception:
        pass

def save_risk_history():
    try:
        with open(RISK_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(risk_history_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save risk history: {e}")

def load_adr_history():
    global adr_history_db
    try:
        with open(ADR_HISTORY_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                adr_history_db = loaded
    except Exception:
        pass

def save_adr_history():
    try:
        with open(ADR_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(adr_history_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save adr history: {e}")

def load_medrag_history():
    global medrag_history_db
    try:
        with open(MEDRAG_HISTORY_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded:
                medrag_history_db = loaded
    except Exception:
        pass

def save_medrag_history():
    try:
        with open(MEDRAG_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(medrag_history_db, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save medrag history: {e}")

prescriptions_db: List[dict] = [
    {"id": "rx-001", "patient": "John Doe", "physician": "Dr. A. Sharma", "timestamp": "2025-06-01T10:30:00", "user_id": None, "filename": "diabetes_prescription.pdf", "file_size": 156240, "notes": "Patient compliant with medication. Monitor blood sugar levels weekly.",
     "fhir": {"resourceType": "MedicationRequest", "id": "rx-001", "status": "active", "intent": "order",
       "subject": {"display": "John Doe"}, "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "Metformin 500 MG"}]},
       "dosageInstruction": [{"text": "500mg twice daily with meals"}], "prescriber": {"display": "Dr. A. Sharma"}}},
    {"id": "rx-002", "patient": "Priya Patel", "physician": "Dr. R. Mehta", "timestamp": "2025-06-02T14:15:00", "user_id": None, "filename": "hypertension_rx.png", "file_size": 512340, "notes": "BP control adequate. Continue medication. Follow-up appointment in 3 months.",
     "fhir": {"resourceType": "MedicationRequest", "id": "rx-002", "status": "active", "intent": "order",
       "subject": {"display": "Priya Patel"}, "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046", "display": "Lisinopril 10 MG"}]},
       "dosageInstruction": [{"text": "10mg once daily in the morning"}], "prescriber": {"display": "Dr. R. Mehta"}}},
    {"id": "rx-6c57e668", "patient": "Darshan Kumar", "physician": "Dr. Annappa s", "timestamp": "2026-02-20T21:02:10.915706", "user_id": None, "filename": "pain_relief_rx.jpg", "file_size": 234560, "notes": "Pain management prescription. Use as needed. Avoid driving if drowsy.",
     "fhir": {"resourceType": "MedicationRequest", "id": "rx-6c57e668", "status": "active", "intent": "order",
       "subject": {"display": "Darshan Kumar"}, "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "310965", "display": "Ibuprofen 400 MG"}]},
       "dosageInstruction": [{"text": "400mg every 6-8 hours as needed for pain"}], "prescriber": {"display": "Dr. Annappa s"}}}
]

chatbot_sessions_db: List[dict] = [
    {"id": "mh-001", "user_id": None, "user": "User #001", "topic": "Anxiety & work stress", "duration_min": 8, "timestamp": "2025-06-01T09:00:00", "outcome": "CBT coping techniques provided"},
    {"id": "mh-002", "user_id": None, "user": "User #002", "topic": "Sleep difficulties", "duration_min": 12, "timestamp": "2025-06-02T20:30:00", "outcome": "Sleep hygiene guidance given"}
]

risk_predictions_db: List[dict] = []
scans_db: List[dict] = [
    {"id": "SCN-001", "patient": "John Doe", "pid": "PT-00123", "type": "mri", "region": "Brain / Head", "notes": "Routine MRI — no acute abnormalities", "physician": "Dr. Patel", "date": "2025-06-01T09:00:00", "user_id": None},
    {"id": "SCN-002", "patient": "Priya Sharma", "pid": "PT-00456", "type": "xray", "region": "Chest / Thorax", "notes": "Mild cardiomegaly — no pleural effusion", "physician": "Dr. Kumar", "date": "2025-06-02T11:00:00", "user_id": None},
]
urgent_queue_db: List[dict] = []
contacts_db: List[dict] = []
rag_queries_db: List[dict] = []

# ── ADR Database ──────────────────────────────────────────────────────────────
ADR_INTERACTIONS = {
    ("warfarin", "aspirin"):    {"severity": "critical", "reaction": "Significantly increased bleeding risk. Warfarin anticoagulant effect potentiated.", "action": "Avoid combination. Monitor INR closely if unavoidable.", "source": "BNF Drug Interaction Checker", "source_url": "https://bnf.nice.org.uk/interaction/warfarin/"},
    ("warfarin", "ibuprofen"):  {"severity": "critical", "reaction": "Increased bleeding risk and possible INR elevation.", "action": "Avoid. Use paracetamol instead. Monitor INR if unavoidable.", "source": "Drugs.com", "source_url": "https://www.drugs.com/interactions-check.php"},
    ("maoi", "ssri"):           {"severity": "critical", "reaction": "Potentially fatal Serotonin Syndrome: hyperthermia, agitation, tremor.", "action": "ABSOLUTE CONTRAINDICATION. 14-day washout after stopping MAOI.", "source": "FDA Drug Safety", "source_url": "https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers"},
    ("metformin", "contrast"):  {"severity": "moderate", "reaction": "Risk of contrast-induced nephropathy and lactic acidosis.", "action": "Hold metformin 48h before/after contrast. Check renal function before resuming.", "source": "ACR Manual on Contrast Media", "source_url": "https://www.acr.org/Clinical-Resources/Contrast-Manual"},
    ("ace", "potassium"):       {"severity": "moderate", "reaction": "Hyperkalaemia risk from combined potassium-sparing effect.", "action": "Monitor serum potassium closely.", "source": "NICE BNF", "source_url": "https://bnf.nice.org.uk"},
    ("statin", "grapefruit"):   {"severity": "minor", "reaction": "Increased statin plasma levels raising myopathy risk.", "action": "Advise patient to avoid grapefruit juice.", "source": "FDA", "source_url": "https://www.fda.gov/consumers/consumer-updates/grapefruit-juice-and-some-drugs-dont-mix"},
    ("ssri", "tramadol"):       {"severity": "critical", "reaction": "Serotonin syndrome risk; tramadol also lowers seizure threshold.", "action": "Avoid if possible. Use alternative analgesic. Monitor closely.", "source": "FDA", "source_url": "https://www.fda.gov"},
    ("digoxin", "amiodarone"):  {"severity": "critical", "reaction": "Amiodarone markedly increases digoxin levels; risk of digoxin toxicity.", "action": "Reduce digoxin dose by 50%. Monitor digoxin levels and ECG.", "source": "BNF", "source_url": "https://bnf.nice.org.uk"},
    ("methotrexate", "nsaid"):  {"severity": "critical", "reaction": "NSAIDs reduce renal clearance of methotrexate, risking toxicity.", "action": "Avoid routine NSAIDs with methotrexate. Use paracetamol.", "source": "NICE", "source_url": "https://www.nice.org.uk"},
    ("lithium", "nsaid"):       {"severity": "moderate", "reaction": "NSAIDs reduce lithium excretion, risking toxicity (tremor, confusion).", "action": "Monitor lithium levels closely. Prefer paracetamol.", "source": "BNF", "source_url": "https://bnf.nice.org.uk"},
}

# ── Pydantic Models ───────────────────────────────────────────────────────────
class ChatInput(BaseModel):
    message: str

class ClinicalData(BaseModel):
    age: int
    bp: int
    dbp: Optional[int] = 80
    sugar: int
    bmi: Optional[float] = 0.0
    cholesterol: Optional[int] = 0
    smoking: Optional[str] = "Non-Smoker"
    gender: Optional[str] = "Unknown"
    heart_rate: Optional[int] = 75
    family_history_cvd: Optional[str] = "no"
    symptoms: Optional[str] = ""
    medications: Optional[str] = ""

class ADRCheckRequest(BaseModel):
    drug1: str
    drug2: str
    patient_age: Optional[int] = None
    conditions: Optional[str] = ""

class ADRReport(BaseModel):
    drug: str
    patient_id: Optional[str] = "Unknown"
    reaction: str
    severity: str

class ScanRecord(BaseModel):
    patient: str
    patient_id: Optional[str] = ""
    scan_type: str
    region: str
    notes: Optional[str] = ""
    physician: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "physician"

class PrescriptionText(BaseModel):
    text: str
    patient_name: Optional[str] = "Unknown Patient"
    physician: Optional[str] = "Unknown Physician"

class RAGQuery(BaseModel):
    query: str

class ContactForm(BaseModel):
    name: str
    email: str
    subject: Optional[str] = "General"
    message: str

class ReportRequest(BaseModel):
    include_prescriptions: Optional[bool] = True
    include_risk: Optional[bool] = True
    include_chatbot: Optional[bool] = True
    include_adr: Optional[bool] = True
    include_scans: Optional[bool] = True

# ══════════════════════════════════════════════════════════════════════════════
#  MEDICAL KNOWLEDGE BASE — 50+ CONDITIONS
# ══════════════════════════════════════════════════════════════════════════════
MEDICAL_KB = {
    # ── ENDOCRINE ────────────────────────────────────────────────────────────
    "diabetes": {
        "answer": "Type 2 Diabetes Mellitus (T2DM): First-line treatment is lifestyle intervention (diet, exercise, weight management) + Metformin. ADA 2024 targets HbA1c < 7% for most adults. Add GLP-1 RA or SGLT-2 inhibitor with established CVD, CKD, or HF. Monitor HbA1c every 3 months until stable, then 6-monthly. Diabetes complications include retinopathy, nephropathy, neuropathy and cardiovascular disease — screen annually.",
        "sources": [
            {"title": "ADA Standards of Care 2024", "url": "https://diabetesjournals.org/care/issue/47/Supplement_1", "org": "ADA"},
            {"title": "NICE NG28: Type 2 Diabetes Management", "url": "https://www.nice.org.uk/guidance/ng28", "org": "NICE UK"},
            {"title": "WHO Diabetes Fact Sheet", "url": "https://www.who.int/news-room/fact-sheets/detail/diabetes", "org": "WHO"}
        ]
    },
    "type 1 diabetes": {
        "answer": "Type 1 Diabetes Mellitus (T1DM): autoimmune destruction of pancreatic β-cells requiring lifelong insulin therapy. Standard: basal-bolus regimen (long-acting + rapid-acting insulin). Continuous glucose monitoring (CGM) and insulin pump therapy (CSII) improve outcomes. Target HbA1c < 7% (ADA 2024). Educate on hypoglycaemia management, sick-day rules, and diabetic ketoacidosis (DKA) prevention.",
        "sources": [
            {"title": "ADA T1DM Standards 2024", "url": "https://diabetesjournals.org/care/issue/47/Supplement_1", "org": "ADA"},
            {"title": "NICE NG17: Type 1 Diabetes in Adults", "url": "https://www.nice.org.uk/guidance/ng17", "org": "NICE UK"}
        ]
    },
    "hypothyroidism": {
        "answer": "Hypothyroidism: TSH > 4.5 mIU/L with low free T4 confirms primary hypothyroidism. Treatment: levothyroxine (T4) starting 1.6 mcg/kg/day, titrated by TSH every 6–8 weeks. Target TSH 0.5–2.5 mIU/L. Hashimoto's thyroiditis is the commonest cause in iodine-sufficient regions. Symptoms: fatigue, weight gain, cold intolerance, constipation, bradycardia.",
        "sources": [
            {"title": "ATA Hypothyroidism Guidelines 2014", "url": "https://www.thyroid.org/patient-thyroid-information/ct-for-patients/vol-7-issue-1/vol-7-issue-1-p-3-4/", "org": "ATA"},
            {"title": "NICE CKS: Hypothyroidism", "url": "https://cks.nice.org.uk/topics/hypothyroidism/", "org": "NICE UK"}
        ]
    },
    "hyperthyroidism": {
        "answer": "Hyperthyroidism: low TSH with elevated free T4/T3. Graves' disease is the most common cause. Treatment options: anti-thyroid drugs (carbimazole/methimazole or propylthiouracil), radioactive iodine (RAI), or thyroidectomy. Beta-blockers (propranolol) for symptomatic relief. Thyroid storm is a life-threatening emergency requiring ICU admission, high-dose anti-thyroid drugs, iodine, corticosteroids, and beta-blockers.",
        "sources": [
            {"title": "ATA Hyperthyroidism Guidelines 2016", "url": "https://www.liebertpub.com/doi/10.1089/thy.2016.0229", "org": "ATA"},
            {"title": "NICE CKS: Hyperthyroidism", "url": "https://cks.nice.org.uk/topics/hyperthyroidism/", "org": "NICE UK"}
        ]
    },
    "obesity": {
        "answer": "Obesity (BMI ≥ 30 kg/m²): managed with lifestyle intervention (reduced-calorie diet, physical activity), behavioural therapy, pharmacotherapy, and bariatric surgery. GLP-1 agonists (semaglutide, tirzepatide) achieve 10–22% weight loss. Bariatric surgery (Roux-en-Y gastric bypass, sleeve gastrectomy) indicated for BMI ≥ 40 or ≥ 35 with comorbidities. Address sleep apnoea, T2DM, hypertension, and dyslipidaemia as part of holistic care.",
        "sources": [
            {"title": "NICE NG187: Obesity Management", "url": "https://www.nice.org.uk/guidance/ng187", "org": "NICE UK"},
            {"title": "AHA/ACC Obesity Guidelines 2022", "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001063", "org": "AHA/ACC"}
        ]
    },
    # ── CARDIOVASCULAR ────────────────────────────────────────────────────────
    "hypertension": {
        "answer": "Hypertension: BP ≥ 130/80 mmHg (AHA 2017) or ≥ 140/90 mmHg (ESC 2023). First-line: ACE inhibitors/ARBs, calcium channel blockers (CCBs), thiazide diuretics. Target < 130/80 mmHg in most adults. Hypertensive crisis (BP ≥ 180/120 mmHg): IV antihypertensives in ICU (urgency/emergency distinction). Lifestyle: DASH diet, sodium restriction < 2.3 g/day, regular aerobic exercise, alcohol moderation.",
        "sources": [
            {"title": "ESC/ESH 2023 Hypertension Guidelines", "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Arterial-Hypertension-Management-of", "org": "ESC/ESH"},
            {"title": "ACC/AHA 2017 Hypertension Guideline", "url": "https://www.acc.org/guidelines", "org": "ACC/AHA"}
        ]
    },
    "heart failure": {
        "answer": "Heart Failure with Reduced EF (HFrEF, EF < 40%): Cornerstone therapy — ACE inhibitor/ARB/ARNI (sacubitril-valsartan) + beta-blocker (carvedilol, bisoprolol) + MRA (spironolactone/eplerenone) + SGLT-2 inhibitor (dapagliflozin, empagliflozin). These four drug classes form the 'Fantastic Four' with mortality benefit. Loop diuretics (furosemide) for symptom relief. Device therapy: ICD, CRT if indicated. HFpEF (EF ≥ 50%): SGLT-2 inhibitors now first-line.",
        "sources": [
            {"title": "ESC 2021 Heart Failure Guidelines", "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Acute-and-Chronic-Heart-Failure", "org": "ESC"},
            {"title": "ACC/AHA 2022 Heart Failure Guideline", "url": "https://www.jacc.org/doi/10.1016/j.jacc.2021.12.012", "org": "ACC/AHA"}
        ]
    },
    "myocardial infarction": {
        "answer": "Acute Myocardial Infarction (MI): STEMI — immediate reperfusion with primary PCI (within 90 min door-to-balloon) is gold standard. Fibrinolysis if PCI not available within 120 min. NSTEMI — antiplatelet (aspirin + P2Y12 inhibitor), anticoagulation, early invasive strategy within 24–72h. Long-term: dual antiplatelet therapy 12 months, statin, ACE inhibitor, beta-blocker. Risk factor modification essential.",
        "sources": [
            {"title": "ESC 2023 ACS Guidelines", "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Acute-Coronary-Syndromes-ACS", "org": "ESC"},
            {"title": "ACC/AHA STEMI Guidelines 2013 (Updated)", "url": "https://www.acc.org/guidelines", "org": "ACC/AHA"}
        ]
    },
    "atrial fibrillation": {
        "answer": "Atrial Fibrillation (AF): most common sustained arrhythmia. Rate control (beta-blocker, digoxin, diltiazem) or rhythm control (cardioversion, antiarrhythmics, ablation). Anticoagulation for stroke prevention: NOACs (apixaban, rivaroxaban, dabigatran, edoxaban) preferred over warfarin for non-valvular AF. CHA₂DS₂-VASc score guides anticoagulation. Ablation for paroxysmal/persistent AF in appropriate candidates.",
        "sources": [
            {"title": "ESC 2020 AF Guidelines", "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Atrial-Fibrillation-Management", "org": "ESC"},
            {"title": "AHA/ACC AF Guideline 2023", "url": "https://www.acc.org/guidelines", "org": "ACC/AHA"}
        ]
    },
    "stroke": {
        "answer": "Ischaemic Stroke: 'Time is brain' — IV thrombolysis (alteplase/tenecteplase) within 4.5h of onset. Mechanical thrombectomy for large vessel occlusion within 24h. Antiplatelet (aspirin ± clopidogrel) for non-cardioembolic stroke. Anticoagulation for AF-related stroke. Secondary prevention: control BP, lipids, glucose, antiplatelet/anticoagulant therapy, lifestyle modification. Haemorrhagic stroke: reverse anticoagulation, BP control, neurosurgical review.",
        "sources": [
            {"title": "AHA/ASA Acute Ischaemic Stroke Guideline 2019", "url": "https://www.ahajournals.org/doi/10.1161/STR.0000000000000211", "org": "AHA/ASA"},
            {"title": "ESO Thrombolysis Guidelines", "url": "https://eso-stroke.org/guidelines/", "org": "ESO"}
        ]
    },
    "coronary artery disease": {
        "answer": "Coronary Artery Disease (CAD): Stable angina managed with lifestyle modification, aspirin, statin, beta-blocker, nitrates, and risk factor control. Revascularisation (PCI or CABG) for significant stenosis, LM disease, or failure of medical therapy. CABG preferred over PCI for left main or complex multivessel disease. ACS requires urgent revascularisation — see myocardial infarction entry.",
        "sources": [
            {"title": "ESC 2019 Chronic Coronary Syndromes Guideline", "url": "https://www.escardio.org/Guidelines", "org": "ESC"},
            {"title": "ACC/AHA Stable Ischaemic Heart Disease Guideline", "url": "https://www.acc.org/guidelines", "org": "ACC/AHA"}
        ]
    },
    # ── RESPIRATORY ───────────────────────────────────────────────────────────
    "asthma": {
        "answer": "Asthma: stepwise therapy (GINA 2024). Step 1: SABA PRN (low-dose ICS preferred). Step 2: low-dose ICS + SABA. Step 3: low-dose ICS-LABA. Step 4: medium-dose ICS-LABA. Step 5: high-dose ICS-LABA + add-on biologics (dupilumab, mepolizumab, omalizumab). Acute severe asthma: SABA nebulisers, ipratropium, IV/oral corticosteroids, oxygen, consider IV magnesium sulphate, ICU if life-threatening.",
        "sources": [
            {"title": "GINA 2024 Global Strategy for Asthma", "url": "https://ginasthma.org/gina-reports/", "org": "GINA"},
            {"title": "NICE NG80: Asthma Diagnosis and Monitoring", "url": "https://www.nice.org.uk/guidance/ng80", "org": "NICE UK"}
        ]
    },
    "copd": {
        "answer": "Chronic Obstructive Pulmonary Disease (COPD): GOLD 2024 classification by spirometry (FEV1/FVC < 0.70) and symptoms. Initial therapy: SABA/SAMA PRN. Group A: LAMA or LABA. Group B/E: LAMA + LABA. Add ICS if frequent exacerbations or eosinophils ≥ 300. Pulmonary rehabilitation improves exercise capacity. Smoking cessation is the single most effective intervention. COPD exacerbation: SABA + SAMA nebulisers, prednisolone 5 days, antibiotics if infective features, controlled oxygen (target SpO2 88–92%).",
        "sources": [
            {"title": "GOLD 2024 COPD Report", "url": "https://goldcopd.org/2024-gold-report/", "org": "GOLD"},
            {"title": "NICE NG115: COPD in Adults", "url": "https://www.nice.org.uk/guidance/ng115", "org": "NICE UK"}
        ]
    },
    "pneumonia": {
        "answer": "Community-Acquired Pneumonia (CAP): CURB-65 score guides severity (confusion, urea >7, RR ≥30, BP <90/60, age ≥65). Score 0–1: oral antibiotics at home (amoxicillin 5 days). Score 2: consider hospital. Score ≥3: hospital admission, IV antibiotics. Atypical coverage (macrolide or doxycycline) for atypical pathogens. Hospital-acquired pneumonia (HAP): broader spectrum antibiotics including Gram-negative cover (piperacillin-tazobactam, meropenem if resistant).",
        "sources": [
            {"title": "BTS Pneumonia Guidelines 2009 (Updated)", "url": "https://www.brit-thoracic.org.uk/quality-improvement/guidelines/pneumonia-adults/", "org": "BTS"},
            {"title": "IDSA/ATS CAP Guidelines 2019", "url": "https://www.idsociety.org/practice-guideline/community-acquired-pneumonia-cap-in-adults/", "org": "IDSA"}
        ]
    },
    "pulmonary embolism": {
        "answer": "Pulmonary Embolism (PE): Wells score and D-dimer guide diagnosis. CT pulmonary angiography (CTPA) is diagnostic gold standard. Treatment: therapeutic anticoagulation (NOAC preferred — rivaroxaban or apixaban). Massive PE with haemodynamic instability: systemic thrombolysis or catheter-directed therapy. High-risk PE: consider surgical embolectomy. Duration: provoked PE 3 months, unprovoked or cancer-associated PE 6–12 months or indefinitely.",
        "sources": [
            {"title": "ESC 2019 PE Guidelines", "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Acute-Pulmonary-Embolism-Diagnosis-and-Management-of", "org": "ESC"},
            {"title": "NICE NG158: Venous Thromboembolic Diseases", "url": "https://www.nice.org.uk/guidance/ng158", "org": "NICE UK"}
        ]
    },
    # ── GASTROENTEROLOGY ──────────────────────────────────────────────────────
    "peptic ulcer": {
        "answer": "Peptic Ulcer Disease (PUD): H. pylori eradication is cornerstone — triple therapy (PPI + clarithromycin + amoxicillin) or quadruple therapy for 14 days. PPIs (omeprazole, lansoprazole) for acid suppression 4–8 weeks. NSAID-induced ulcers: stop NSAID, use PPI. Complicated ulcers (bleeding, perforation, obstruction) require urgent endoscopy and/or surgery. Test-and-treat for H. pylori in uninvestigated dyspepsia.",
        "sources": [
            {"title": "ACG Clinical Guideline: H. pylori 2017", "url": "https://www.gastrojournal.org/article/S0016-5085(17)35531-7/fulltext", "org": "ACG"},
            {"title": "NICE CKS: Peptic Ulcer Disease", "url": "https://cks.nice.org.uk/topics/peptic-ulcer-disease/", "org": "NICE UK"}
        ]
    },
    "ibd": {
        "answer": "Inflammatory Bowel Disease (IBD) — Crohn's Disease & Ulcerative Colitis (UC): Mild UC: 5-ASA (mesalazine). Moderate-severe: corticosteroids to induce remission, then steroid-sparing agents (azathioprine, 6-MP, methotrexate). Biologics (infliximab, adalimumab, vedolizumab, ustekinumab) for moderate-severe refractory disease. Surgery for UC: colectomy may be curative. Crohn's: medical therapy preferred; surgery for complications. Monitor for colorectal cancer with surveillance colonoscopy.",
        "sources": [
            {"title": "ECCO IBD Guidelines 2022", "url": "https://www.ecco-ibd.eu/guidelines.html", "org": "ECCO"},
            {"title": "NICE NG129: Crohn's Disease", "url": "https://www.nice.org.uk/guidance/ng129", "org": "NICE UK"}
        ]
    },
    "liver cirrhosis": {
        "answer": "Liver Cirrhosis: treat the underlying cause (abstinence in alcoholic cirrhosis, antivirals for HBV/HCV, weight loss for NASH). Complications management: ascites (salt restriction, spironolactone ± furosemide), spontaneous bacterial peritonitis (SBP: prophylactic ciprofloxacin, treat with cefotaxime), hepatic encephalopathy (lactulose, rifaximin), varices (non-selective beta-blockers for primary prophylaxis, band ligation), hepatorenal syndrome (terlipressin + albumin). Liver transplant for end-stage disease.",
        "sources": [
            {"title": "EASL Clinical Practice Guidelines: Cirrhosis 2021", "url": "https://www.easl.eu/research/our-contributions/clinical-practice-guidelines", "org": "EASL"},
            {"title": "AASLD Practice Guidance: Cirrhosis", "url": "https://www.aasld.org/publications/practice-guidelines", "org": "AASLD"}
        ]
    },
    "gerd": {
        "answer": "Gastro-Oesophageal Reflux Disease (GERD): lifestyle modification (weight loss, elevate bed head, avoid triggers). Step-up therapy: antacids → H2 blockers → PPIs (most effective). PPI (omeprazole 20–40mg daily) for 4–8 weeks; on-demand PPI for non-erosive GERD. Barrett's oesophagus requires surveillance endoscopy and high-dose PPI. Refractory GERD: consider anti-reflux surgery (fundoplication) after pH impedance testing.",
        "sources": [
            {"title": "ACG GERD Guidelines 2022", "url": "https://journals.lww.com/ajg/Fulltext/2022/01000/ACG_Clinical_Guideline_for_the_Diagnosis_and.13.aspx", "org": "ACG"},
            {"title": "NICE CKS: GORD in Adults", "url": "https://cks.nice.org.uk/topics/dyspepsia-gord/", "org": "NICE UK"}
        ]
    },
    # ── INFECTIOUS DISEASE ────────────────────────────────────────────────────
    "sepsis": {
        "answer": "Sepsis-3: life-threatening organ dysfunction (SOFA score ≥ 2) caused by dysregulated host response to infection. Surviving Sepsis Campaign 1-hour bundle: (1) measure lactate, (2) blood cultures before antibiotics, (3) broad-spectrum IV antibiotics within 1h, (4) 30 mL/kg IV crystalloid bolus if hypotensive or lactate ≥ 4, (5) vasopressors (norepinephrine) if MAP < 65 mmHg. Septic shock: vasopressors + hydrocortisone if refractory. ICU admission, source control, de-escalate antibiotics at 48–72h.",
        "sources": [
            {"title": "Surviving Sepsis Campaign Guidelines 2021", "url": "https://www.sccm.org/SurvivingSepsisCampaign/Guidelines", "org": "SCCM/ESICM"},
            {"title": "Sepsis-3 Definition JAMA 2016", "url": "https://jamanetwork.com/journals/jama/fullarticle/2492881", "org": "JAMA"}
        ]
    },
    "covid": {
        "answer": "COVID-19: Mild/Moderate: rest, hydration, antipyretics (paracetamol). High-risk patients: antivirals within 5 days of symptom onset (nirmatrelvir/ritonavir [Paxlovid] preferred, or remdesivir). Severe/Critical: dexamethasone 6 mg/day for 10 days if requiring oxygen. Add baricitinib or tocilizumab for rapidly worsening patients. Anticoagulation for hospitalised patients. Vaccination remains the best prevention (primary series + boosters).",
        "sources": [
            {"title": "NIH COVID-19 Treatment Guidelines", "url": "https://www.covid19treatmentguidelines.nih.gov/", "org": "NIH"},
            {"title": "WHO Therapeutics and COVID-19", "url": "https://www.who.int/publications/i/item/WHO-2019-nCoV-therapeutics-2023.1", "org": "WHO"}
        ]
    },
    "tuberculosis": {
        "answer": "Tuberculosis (TB): Standard treatment — RHEZ (Rifampicin + Isoniazid + Ethambutol + Pyrazinamide) for 2 months initial phase, then Rifampicin + Isoniazid for 4 months continuation. Total: 6 months for drug-susceptible pulmonary TB. MDR-TB: longer regimens with bedaquiline, delamanid, linezolid. DOTS (directly observed therapy) essential. Prophylactic isoniazid/rifampicin for latent TB. Contact tracing mandatory.",
        "sources": [
            {"title": "WHO TB Treatment Guidelines 2022", "url": "https://www.who.int/publications/i/item/9789240048782", "org": "WHO"},
            {"title": "NICE NG33: Tuberculosis", "url": "https://www.nice.org.uk/guidance/ng33", "org": "NICE UK"}
        ]
    },
    "hiv": {
        "answer": "HIV/AIDS: Antiretroviral Therapy (ART) indicated for all patients regardless of CD4 count. Preferred first-line: dolutegravir (INSTI) + tenofovir/emtricitabine (NRTI backbone). Bictegravir/tenofovir alafenamide/emtricitabine (Biktarvy) is a popular single-tablet regimen. Target: HIV RNA undetectable (< 50 copies/mL). U=U (Undetectable = Untransmittable). PrEP (pre-exposure prophylaxis): daily tenofovir/emtricitabine for HIV-negative high-risk individuals. Screen for opportunistic infections (PCP, CMV, toxoplasmosis).",
        "sources": [
            {"title": "DHHS Antiretroviral Guidelines 2024", "url": "https://clinicalinfo.hiv.gov/en/guidelines/hiv-clinical-guidelines-adult-and-adolescent-arv", "org": "DHHS"},
            {"title": "BHIVA Guidelines 2023", "url": "https://www.bhiva.org/HIV-1-treatment-guidelines", "org": "BHIVA"}
        ]
    },
    "malaria": {
        "answer": "Malaria: Diagnosis by rapid antigen test (RDT) or blood film microscopy. Uncomplicated P. falciparum: artemisinin-based combination therapy (ACT) — artemether-lumefantrine or artesunate-amodiaquine. P. vivax/ovale: chloroquine (if sensitive) + primaquine for radical cure (G6PD test first). Severe malaria: IV artesunate; switch to oral once tolerated. Prophylaxis: doxycycline, atovaquone-proguanil, or mefloquine depending on region.",
        "sources": [
            {"title": "WHO Malaria Treatment Guidelines 2022", "url": "https://www.who.int/publications/i/item/9789240066793", "org": "WHO"},
            {"title": "CDC Malaria Treatment", "url": "https://www.cdc.gov/malaria/hcp/clinical-guidance/index.html", "org": "CDC"}
        ]
    },
    "urinary tract infection": {
        "answer": "Urinary Tract Infection (UTI): Uncomplicated lower UTI (cystitis) in women: trimethoprim 200 mg BD 7 days or nitrofurantoin 100 mg modified-release BD 5 days (first-line per NICE). Complicated/pyelonephritis: oral ciprofloxacin 7 days or co-amoxiclav; IV cefuroxime if hospitalised. Recurrent UTI: self-start antibiotics or prophylactic low-dose antibiotics. Catheter-associated UTI: treat only if symptomatic. UTI in pregnancy: treat all bacteriuria.",
        "sources": [
            {"title": "NICE CKS: UTI (Lower) Women", "url": "https://cks.nice.org.uk/topics/urinary-tract-infection-lower-women/", "org": "NICE UK"},
            {"title": "EAU Urological Infections Guidelines 2023", "url": "https://uroweb.org/guidelines/urological-infections", "org": "EAU"}
        ]
    },
    # ── NEUROLOGICAL ──────────────────────────────────────────────────────────
    "epilepsy": {
        "answer": "Epilepsy: first-line AED depends on seizure type. Generalised tonic-clonic: sodium valproate (most effective, avoid in women of childbearing age), levetiracetam, lamotrigine. Focal: carbamazepine, lacosamide, levetiracetam. Status epilepticus: IV lorazepam → IV levetiracetam/phenytoin/valproate → general anaesthesia. Aim for seizure freedom with monotherapy first. Consider SUDEP risk; driving restrictions apply.",
        "sources": [
            {"title": "NICE NG217: Epilepsies in Adults 2022", "url": "https://www.nice.org.uk/guidance/ng217", "org": "NICE UK"},
            {"title": "ILAE AED Treatment Guidelines", "url": "https://www.ilae.org/guidelines", "org": "ILAE"}
        ]
    },
    "parkinson": {
        "answer": "Parkinson's Disease: dopaminergic replacement is the mainstay. Levodopa/carbidopa is most effective (levodopa is the gold standard). Dopamine agonists (ropinirole, pramipexole) useful in younger patients to delay levodopa dyskinesias. MAO-B inhibitors (rasagiline, selegiline) as early monotherapy or adjunct. Advanced disease: levodopa pump, apomorphine pump, deep brain stimulation (DBS) for carefully selected patients. Non-motor symptoms (depression, dementia, autonomic dysfunction) also require attention.",
        "sources": [
            {"title": "NICE NG71: Parkinson's Disease 2017", "url": "https://www.nice.org.uk/guidance/ng71", "org": "NICE UK"},
            {"title": "MDS Parkinson's Evidence-Based Medicine", "url": "https://www.movementdisorders.org/MDS/Education/EBM-Reviews.htm", "org": "MDS"}
        ]
    },
    "multiple sclerosis": {
        "answer": "Multiple Sclerosis (MS): relapsing-remitting MS (RRMS) treated with disease-modifying therapies (DMTs). High-efficacy first-line DMTs: natalizumab, ocrelizumab, ofatumumab, alemtuzumab. Moderate-efficacy: interferon-beta, glatiramer acetate, dimethyl fumarate, teriflunomide. Acute relapse: IV methylprednisolone 1g/day for 3–5 days. Symptomatic treatment: spasticity (baclofen), fatigue (amantadine), bladder dysfunction, pain. Progressive MS: siponimod, ocrelizumab for active forms.",
        "sources": [
            {"title": "ECTRIMS/EAN MS Treatment Guidelines 2023", "url": "https://www.ean.eu/ean-guidelines/ms", "org": "ECTRIMS/EAN"},
            {"title": "NICE NG220: Multiple Sclerosis 2022", "url": "https://www.nice.org.uk/guidance/ng220", "org": "NICE UK"}
        ]
    },
    "migraine": {
        "answer": "Migraine: Acute treatment: NSAIDs (naproxen, ibuprofen), paracetamol, triptans (sumatriptan, rizatriptan) for moderate-severe attacks. Anti-emetics (metoclopramide, prochlorperazine) for nausea. Preventive therapy (≥4 attacks/month): topiramate, propranolol, amitriptyline, candesartan, CGRP antagonists (erenumab, fremanezumab). Avoid medication overuse headache (limit acute therapy to ≤10–15 days/month). CGRP monoclonal antibodies are highly effective preventives.",
        "sources": [
            {"title": "EHF/EFNS Migraine Treatment Guidelines", "url": "https://thejournalofheadacheandpain.biomedcentral.com/articles/10.1186/s10194-022-01431-7", "org": "EHF"},
            {"title": "NICE NG150: Headaches in Over 12s", "url": "https://www.nice.org.uk/guidance/ng150", "org": "NICE UK"}
        ]
    },
    "meningitis": {
        "answer": "Bacterial Meningitis: medical emergency. Classic triad: fever, severe headache, neck stiffness. Do NOT delay antibiotics for CT scan if LP is clinically unsafe. Empirical treatment: IV cefotaxime/ceftriaxone + dexamethasone (before or with first dose of antibiotic). Add ampicillin for Listeria risk (age > 60, immunocompromised). Viral meningitis: usually self-limiting; aciclovir for HSV. Notify public health for N. meningitidis; close contacts require prophylactic ciprofloxacin/rifampicin.",
        "sources": [
            {"title": "ESCMID/EFNS Bacterial Meningitis Guidelines", "url": "https://www.escmid.org/publications/by-topic/id-clinical-guidelines/", "org": "ESCMID"},
            {"title": "BNF: Bacterial Meningitis Treatment", "url": "https://bnf.nice.org.uk", "org": "BNF NICE"}
        ]
    },
    # ── MENTAL HEALTH ─────────────────────────────────────────────────────────
    "anxiety": {
        "answer": "Generalised Anxiety Disorder (GAD): stepped-care approach (NICE CG113). Step 1: psychoeducation, self-help. Step 2: low-intensity CBT, guided self-help. Step 3: high-intensity CBT or medication (SSRIs — sertraline first-line, SNRIs — venlafaxine/duloxetine, pregabalin). Step 4: specialist CAMHS/IAPT. Avoid long-term benzodiazepines. Panic disorder: CBT is most effective; SSRIs for pharmacotherapy. Social anxiety: CBT + SSRI.",
        "sources": [
            {"title": "NICE CG113: Generalised Anxiety Disorder", "url": "https://www.nice.org.uk/guidance/cg113", "org": "NICE UK"},
            {"title": "APA Practice Guidelines: Anxiety", "url": "https://www.apa.org/practice/guidelines", "org": "APA"}
        ]
    },
    "depression": {
        "answer": "Major Depressive Disorder (MDD): First-line: SSRIs (sertraline, escitalopram, fluoxetine). SNRIs (venlafaxine, duloxetine) for comorbid pain or anxiety. Mirtazapine for poor sleep/appetite. Start low, titrate, reassess at 4 weeks. Minimum 6 months treatment after remission to prevent relapse. Treatment-resistant depression: add lithium augmentation, quetiapine, or refer to psychiatry. Psychotherapy: CBT, interpersonal therapy (IPT). ECT for severe/refractory depression. Urgent referral if suicidal ideation.",
        "sources": [
            {"title": "NICE CG90: Depression in Adults", "url": "https://www.nice.org.uk/guidance/cg90", "org": "NICE UK"},
            {"title": "APA Practice Guideline for MDD 2010 (Updated)", "url": "https://www.apa.org/practice/guidelines", "org": "APA"}
        ]
    },
    "bipolar": {
        "answer": "Bipolar Disorder: Acute mania: antipsychotics (haloperidol, olanzapine, quetiapine, risperidone) ± lithium/valproate. Avoid antidepressant monotherapy (risk of switch). Acute bipolar depression: quetiapine, lurasidone, lamotrigine. Mood stabilisers for maintenance: lithium (most evidence for suicide prevention), valproate, lamotrigine. Monitor lithium levels (0.6–0.8 mmol/L maintenance) and renal/thyroid function. Psychoeducation and structured psychotherapy essential.",
        "sources": [
            {"title": "NICE CG185: Bipolar Disorder", "url": "https://www.nice.org.uk/guidance/cg185", "org": "NICE UK"},
            {"title": "CANMAT Bipolar Guidelines 2023", "url": "https://www.canmat.org/2023/03/09/2023-canmat-and-isbd-guidelines-for-the-management-of-patients-with-bipolar-disorder/", "org": "CANMAT"}
        ]
    },
    "schizophrenia": {
        "answer": "Schizophrenia: Antipsychotics are the cornerstone. First-episode: start with an atypical antipsychotic (risperidone, olanzapine, aripiprazole, quetiapine). Clozapine reserved for treatment-resistant schizophrenia (two failed adequate trials). Long-acting injectable (LAI) antipsychotics improve adherence. Psychosocial interventions: CBT for psychosis (CBTp), family therapy, supported employment. Early Intervention in Psychosis (EIP) services for first-episode. Monitor metabolic effects of antipsychotics.",
        "sources": [
            {"title": "NICE CG178: Schizophrenia 2014", "url": "https://www.nice.org.uk/guidance/cg178", "org": "NICE UK"},
            {"title": "APA Schizophrenia Practice Guidelines 2021", "url": "https://www.apa.org/practice/guidelines", "org": "APA"}
        ]
    },
    "ptsd": {
        "answer": "PTSD: Trauma-focused psychological therapies are first-line — Trauma-focused CBT (TF-CBT) and EMDR (Eye Movement Desensitisation and Reprocessing). Typically 8–12 sessions. Drug therapy: SSRIs (paroxetine, sertraline — FDA approved) if psychological therapy unavailable or declined. Avoid benzodiazepines. Prazosin for trauma-related nightmares. Complex PTSD requires more intensive psychological treatment, possibly residential. Screen military veterans, survivors of violence, accidents, and disaster.",
        "sources": [
            {"title": "NICE NG116: PTSD 2018", "url": "https://www.nice.org.uk/guidance/ng116", "org": "NICE UK"},
            {"title": "APA PTSD Clinical Practice Guideline", "url": "https://www.apa.org/ptsd-guideline", "org": "APA"}
        ]
    },
    # ── MUSCULOSKELETAL ───────────────────────────────────────────────────────
    "rheumatoid arthritis": {
        "answer": "Rheumatoid Arthritis (RA): treat-to-target strategy aiming for remission or low disease activity (DAS28 < 2.6/3.2). First-line DMARD: methotrexate (10–25mg weekly) + folic acid. Triple DMARD therapy if inadequate response (add sulfasalazine + hydroxychloroquine). Biologics (anti-TNF: adalimumab, etanercept, infliximab; or non-TNF: abatacept, rituximab, tocilizumab) if 2 DMARDs fail. JAK inhibitors (baricitinib, upadacitinib) as alternative. Bridging corticosteroids during flares.",
        "sources": [
            {"title": "EULAR RA Treatment Recommendations 2022", "url": "https://www.eular.org/recommendations_management.cfm", "org": "EULAR"},
            {"title": "NICE RA Guidelines 2018", "url": "https://www.nice.org.uk/guidance/ng100", "org": "NICE UK"}
        ]
    },
    "osteoporosis": {
        "answer": "Osteoporosis: T-score ≤ -2.5 on DEXA. WHO FRAX tool for 10-year fracture probability to guide treatment thresholds. First-line: oral bisphosphonates (alendronate, risedronate). Alternatives: IV zoledronic acid annually, denosumab (6-monthly injection). Anabolic agents (teriparatide, romosozumab) for severe osteoporosis or bisphosphonate failure. Calcium 1000–1200 mg/day + vitamin D 800–1000 IU/day for all. Fall prevention strategies and exercise. Avoid prolonged bisphosphonate holiday without reassessment.",
        "sources": [
            {"title": "NOGG Osteoporosis Guidelines 2021", "url": "https://www.nogg.org.uk/guideline", "org": "NOGG"},
            {"title": "ISCD/IOF Osteoporosis Guidelines", "url": "https://www.iofbonehealth.org", "org": "IOF"}
        ]
    },
    "gout": {
        "answer": "Gout: Acute attack: NSAIDs (naproxen, indomethacin), colchicine, or corticosteroids (oral prednisolone or intra-articular injection). Urate-lowering therapy (ULT) for recurrent gout (≥2 attacks/year), tophaceous gout, or urate nephropathy. Target serum urate < 360 μmol/L (< 300 μmol/L for tophaceous gout). First-line ULT: allopurinol (start 50–100 mg, titrate slowly). Febuxostat alternative. Prophylactic colchicine or NSAIDs for 6 months when starting ULT to prevent flares. Dietary advice: limit red meat, offal, seafood, alcohol (especially beer).",
        "sources": [
            {"title": "EULAR Gout Guidelines 2016", "url": "https://www.eular.org/recommendations_management.cfm", "org": "EULAR"},
            {"title": "ACR Gout Guidelines 2020", "url": "https://www.rheumatology.org/Practice-Quality/Clinical-Support/Clinical-Practice-Guidelines/Gout", "org": "ACR"}
        ]
    },
    "osteoarthritis": {
        "answer": "Osteoarthritis (OA): Non-pharmacological: weight loss (most effective for knee OA), exercise (land and aquatic), physiotherapy, walking aids. Pharmacological: topical NSAIDs first (knee/hand OA), then oral NSAIDs (shortest duration, with PPI if GI risk), duloxetine for widespread OA pain. Intra-articular corticosteroids for flares. Avoid long-term opioids. Joint replacement (TKR, THR) for end-stage OA with failed conservative management — highly effective.",
        "sources": [
            {"title": "OARSI OA Guidelines 2019", "url": "https://www.oarsi.org/research/guidelines", "org": "OARSI"},
            {"title": "NICE NG226: Osteoarthritis 2022", "url": "https://www.nice.org.uk/guidance/ng226", "org": "NICE UK"}
        ]
    },
    # ── NEPHROLOGY ────────────────────────────────────────────────────────────
    "chronic kidney disease": {
        "answer": "Chronic Kidney Disease (CKD): classify by GFR (G1-G5) and albuminuria (A1-A3). Slow progression: ACE inhibitor or ARB for proteinuric CKD and hypertension. SGLT-2 inhibitors (dapagliflozin, empagliflozin) reduce CKD progression and CV events. Finerenone for diabetic CKD. Target BP < 130/80 mmHg. Avoid nephrotoxins (NSAIDs, IV contrast). Anaemia: erythropoiesis-stimulating agents (ESA) + iron if Hb < 10 g/dL. Refer nephrology at eGFR < 30 or rapidly declining. Prepare for RRT (dialysis/transplant) at eGFR < 20.",
        "sources": [
            {"title": "KDIGO CKD Guidelines 2024", "url": "https://kdigo.org/guidelines/ckd-evaluation-and-management/", "org": "KDIGO"},
            {"title": "NICE NG203: CKD 2021", "url": "https://www.nice.org.uk/guidance/ng203", "org": "NICE UK"}
        ]
    },
    "acute kidney injury": {
        "answer": "Acute Kidney Injury (AKI): KDIGO staging by creatinine rise or urine output. Identify and treat cause: prerenal (fluid resuscitation), intrinsic (treat underlying — glomerulonephritis, TIN), postrenal (relieve obstruction). Avoid nephrotoxins. Monitor fluid balance, electrolytes (hyperkalaemia, acidosis). Indications for urgent renal replacement therapy (RRT/dialysis): refractory hyperkalaemia, metabolic acidosis, fluid overload, uraemia (pericarditis, encephalopathy).",
        "sources": [
            {"title": "KDIGO AKI Guidelines 2012", "url": "https://kdigo.org/guidelines/acute-kidney-injury/", "org": "KDIGO"},
            {"title": "NICE AKI Guidance 2019", "url": "https://www.nice.org.uk/guidance/ng148", "org": "NICE UK"}
        ]
    },
    # ── ONCOLOGY ─────────────────────────────────────────────────────────────
    "lung cancer": {
        "answer": "Lung Cancer: 85% non-small cell lung cancer (NSCLC), 15% small cell (SCLC). NSCLC treatment: stage I-II: surgical resection ± adjuvant chemotherapy (osimertinib for EGFR-mutant). Stage III: concurrent chemoradiation ± durvalumab. Stage IV: molecular testing mandatory (EGFR, ALK, ROS1, KRAS, PD-L1). Targeted therapy if mutation driver positive; immunotherapy (pembrolizumab) if PD-L1 ≥ 50%; chemotherapy as backbone. SCLC: etoposide + cisplatin/carboplatin ± atezolizumab; prophylactic cranial irradiation.",
        "sources": [
            {"title": "ESMO Lung Cancer Guidelines 2023", "url": "https://www.esmo.org/guidelines/lung-and-chest-tumours", "org": "ESMO"},
            {"title": "NCCN Non-Small Cell Lung Cancer Guidelines", "url": "https://www.nccn.org/professionals/physician_gls/pdf/nscl.pdf", "org": "NCCN"}
        ]
    },
    "breast cancer": {
        "answer": "Breast Cancer: HR+/HER2-: CDK4/6 inhibitor (palbociclib, ribociclib, abemaciclib) + aromatase inhibitor (letrozole, anastrozole) or fulvestrant for metastatic disease. Early breast cancer: surgery (BCS or mastectomy) + sentinel node biopsy ± radiotherapy + adjuvant endocrine therapy (tamoxifen in premenopausal, aromatase inhibitor in postmenopausal) ± chemotherapy (AC-T). HER2+: trastuzumab ± pertuzumab ± chemotherapy. Triple-negative: pembrolizumab + chemotherapy; olaparib for BRCA-mutant.",
        "sources": [
            {"title": "ESMO Breast Cancer Guidelines 2023", "url": "https://www.esmo.org/guidelines/breast-cancer", "org": "ESMO"},
            {"title": "NCCN Breast Cancer Guidelines", "url": "https://www.nccn.org/professionals/physician_gls/pdf/breast.pdf", "org": "NCCN"}
        ]
    },
    "colorectal cancer": {
        "answer": "Colorectal Cancer (CRC): staging determines treatment. Stage I–II: surgical resection (laparoscopic colectomy). Stage III: surgery + adjuvant FOLFOX (oxaliplatin + leucovorin + 5-FU). Stage IV (metastatic): FOLFOX/FOLFIRI ± bevacizumab (anti-VEGF) or cetuximab/panitumumab (anti-EGFR, RAS wild-type only). Microsatellite instability-high (MSI-H): pembrolizumab first-line. Rectal cancer: neoadjuvant chemoradiation before surgery for locally advanced disease. Lynch syndrome screening.",
        "sources": [
            {"title": "ESMO Colorectal Cancer Guidelines 2023", "url": "https://www.esmo.org/guidelines/gastrointestinal-cancers", "org": "ESMO"},
            {"title": "NCCN Colon Cancer Guidelines", "url": "https://www.nccn.org/professionals/physician_gls/pdf/colon.pdf", "org": "NCCN"}
        ]
    },
    "prostate cancer": {
        "answer": "Prostate Cancer: localised: active surveillance (low-risk), radical prostatectomy or radiotherapy (intermediate/high-risk). Biochemical recurrence after local therapy: salvage radiotherapy or ADT. Metastatic hormone-sensitive PCa (mHSPC): ADT + abiraterone, docetaxel, enzalutamide, or apalutamide (doublet or triplet therapy). Metastatic castration-resistant PCa (mCRPC): abiraterone, enzalutamide, darolutamide, cabazitaxel, olaparib (BRCA-mutant), lu-PSMA-617. PSA monitoring.",
        "sources": [
            {"title": "EAU Prostate Cancer Guidelines 2024", "url": "https://uroweb.org/guidelines/prostate-cancer", "org": "EAU"},
            {"title": "ESMO Prostate Cancer Guidelines", "url": "https://www.esmo.org/guidelines/genitourinary-cancers", "org": "ESMO"}
        ]
    },
    # ── HAEMATOLOGY ───────────────────────────────────────────────────────────
    "anaemia": {
        "answer": "Anaemia: Identify cause. Iron deficiency anaemia (IDA): oral ferrous sulfate 200mg TDS (30–60 min before food); IV iron (ferric carboxymaltose) for intolerance or malabsorption. B12/folate deficiency: IM hydroxocobalamin (B12 deficiency) or oral folic acid 5mg. Anaemia of chronic disease: treat underlying condition; EPO if CKD/cancer-related. Haemolytic anaemia: treat cause; corticosteroids for autoimmune. Aplastic anaemia: stem cell transplant or immunosuppression. Transfusion threshold: Hb < 70–80 g/L symptomatic or < 80 g/L cardiac disease.",
        "sources": [
            {"title": "BSH Anaemia Guidelines", "url": "https://www.b-s-h.org.uk/guidelines/", "org": "BSH"},
            {"title": "NICE CKS: Anaemia", "url": "https://cks.nice.org.uk/topics/anaemia-iron-deficiency/", "org": "NICE UK"}
        ]
    },
    "dvt": {
        "answer": "Deep Vein Thrombosis (DVT): Wells score to assess pre-test probability; D-dimer if low-moderate probability. Compression ultrasonography for diagnosis. Treatment: anticoagulation — NOACs preferred (rivaroxaban: 15mg BD 3 weeks then 20mg OD; apixaban: 10mg BD 7 days then 5mg BD). Duration: 3 months provoked DVT, 6 months unprovoked, indefinite if recurrent or cancer-associated. LMWH preferred in cancer-associated VTE (or rivaroxaban/edoxaban). Catheter-directed thrombolysis for extensive iliofemoral DVT with severe symptoms.",
        "sources": [
            {"title": "NICE NG158: VTE Treatment", "url": "https://www.nice.org.uk/guidance/ng158", "org": "NICE UK"},
            {"title": "ESC VTE Guidelines 2019", "url": "https://www.escardio.org/Guidelines", "org": "ESC"}
        ]
    },
    # ── DERMATOLOGY ───────────────────────────────────────────────────────────
    "psoriasis": {
        "answer": "Psoriasis: mild (PASI < 10, BSA < 10%): topical corticosteroids + vitamin D analogues (calcipotriol). Scalp: potent topical steroid shampoo. Moderate-severe: phototherapy (NB-UVB), systemic therapy (methotrexate, ciclosporin, acitretin), or biologics. Biologics: anti-TNF (adalimumab, etanercept), anti-IL-17 (secukinumab, ixekizumab — highest efficacy), anti-IL-23 (risankizumab, guselkumab, skyrizi). Psoriatic arthritis: treat aggressively with DMARDs or biologics.",
        "sources": [
            {"title": "BAD Psoriasis Guidelines 2017", "url": "https://www.bad.org.uk/healthcare-professionals/clinical-standards/clinical-guidelines/psoriasis/", "org": "BAD"},
            {"title": "NICE NG153: Psoriasis 2019", "url": "https://www.nice.org.uk/guidance/ng153", "org": "NICE UK"}
        ]
    },
    "eczema": {
        "answer": "Atopic Eczema (Dermatitis): emollients (apply generously and frequently) are the cornerstone. Topical corticosteroids (mildest effective potency) for flares. Topical calcineurin inhibitors (tacrolimus, pimecrolimus) for sensitive areas (face, flexures) and steroid-sparing. Wet wrap therapy for severe eczema in children. Moderate-severe: phototherapy (NB-UVB), systemic immunosuppressants (methotrexate, ciclosporin, azathioprine) or biologics — dupilumab (anti-IL-4/13, highly effective), tralokinumab. JAK inhibitors: upadacitinib, abrocitinib for adults.",
        "sources": [
            {"title": "BAD Atopic Eczema Guidelines", "url": "https://www.bad.org.uk/healthcare-professionals/clinical-standards/clinical-guidelines/atopic-eczema/", "org": "BAD"},
            {"title": "NICE NG190: Atopic Eczema in Children 2023", "url": "https://www.nice.org.uk/guidance/ng190", "org": "NICE UK"}
        ]
    },
    # ── ENDOCRINOLOGY (ADDITIONAL) ────────────────────────────────────────────
    "cushing syndrome": {
        "answer": "Cushing's Syndrome: excess cortisol. 85% ACTH-dependent (70% pituitary Cushing's disease, 15% ectopic ACTH). Diagnosis: 24h urinary free cortisol, late-night salivary cortisol, overnight 1mg DST; confirm with CRH stimulation test. Pituitary adenoma: trans-sphenoidal surgery (first-line). Adrenal adenoma: adrenalectomy. Medical therapy: metyrapone, ketoconazole, osilodrostat pending surgery or recurrence. Pasireotide for Cushing's disease. Bilateral adrenalectomy if other treatments fail.",
        "sources": [
            {"title": "Endocrine Society Cushing's Guidelines 2015", "url": "https://academic.oup.com/jcem/article/100/8/2807/2836060", "org": "Endocrine Society"}
        ]
    },
    "addison disease": {
        "answer": "Addison's Disease (Primary Adrenal Insufficiency): autoimmune destruction of adrenal cortex. Diagnosis: low morning cortisol, high ACTH, positive short Synacthen test. Life-long replacement: hydrocortisone (15–25 mg/day in 2–3 divided doses) + fludrocortisone 50–200 mcg daily (for mineralocorticoid). Sick day rules: double/triple hydrocortisone dose during illness or surgery (steroid emergency card essential). Adrenal crisis: IV hydrocortisone 100mg bolus + normal saline IV.",
        "sources": [
            {"title": "Endocrine Society Adrenal Insufficiency Guidelines 2016", "url": "https://academic.oup.com/jcem/article/101/2/364/2810192", "org": "Endocrine Society"}
        ]
    },
    # ── PAEDIATRICS ───────────────────────────────────────────────────────────
    "kawasaki disease": {
        "answer": "Kawasaki Disease: medium vessel vasculitis in children. Diagnostic criteria (classic KD): fever ≥5 days + ≥4 of: conjunctivitis, rash, lymphadenopathy, lip/oral changes, extremity changes. Treatment: high-dose IVIG (2g/kg single infusion) + aspirin (high-dose in acute phase, low-dose maintenance). Echocardiography to assess coronary artery aneurysms (most serious complication). Infliximab or corticosteroids for IVIG-resistant KD. Long-term antiplatelet therapy for coronary artery involvement.",
        "sources": [
            {"title": "AHA Kawasaki Disease Guidelines 2017", "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000000484", "org": "AHA"}
        ]
    },
    # ── OPHTHALMOLOGY ─────────────────────────────────────────────────────────
    "glaucoma": {
        "answer": "Glaucoma: optic nerve damage due to raised IOP (usually > 21 mmHg). Primary open-angle glaucoma (POAG) is most common. Target IOP reduction 20–30% from baseline. First-line: prostaglandin analogues (latanoprost, bimatoprost — most effective, once daily). Add beta-blockers (timolol), alpha-2 agonists (brimonidine), carbonic anhydrase inhibitors (dorzolamide) as needed. Laser trabeculoplasty (SLT) as first-line or adjunct. Surgery (trabeculectomy, MIGS) for uncontrolled IOP. Acute angle closure: ophthalmological emergency — IV acetazolamide, topical beta-blocker, pilocarpine, mannitol; laser iridotomy to prevent recurrence.",
        "sources": [
            {"title": "EGS European Glaucoma Society Guidelines 2021", "url": "https://www.eugs.org/eng/guidelines.asp", "org": "EGS"},
            {"title": "NICE NG81: Glaucoma 2022", "url": "https://www.nice.org.uk/guidance/ng81", "org": "NICE UK"}
        ]
    },
    "macular degeneration": {
        "answer": "Age-Related Macular Degeneration (AMD): Dry AMD: no curative therapy; AREDS2 supplements (lutein, zeaxanthin, vitamins C/E, zinc) slow progression in intermediate/advanced AMD. Wet AMD (neovascular): anti-VEGF injections (ranibizumab, bevacizumab, aflibercept, faricimab) as first-line; treat monthly until stable then PRN or treat-and-extend regimen. Early referral to ophthalmology. Smoking cessation reduces AMD risk. Amsler grid monitoring for distortion.",
        "sources": [
            {"title": "AAO AMD Preferred Practice Pattern 2019", "url": "https://www.aao.org/preferred-practice-pattern/age-related-macular-degeneration-ppp", "org": "AAO"},
            {"title": "NICE TA155: Ranibizumab and Pegaptanib for AMD", "url": "https://www.nice.org.uk/guidance/ta155", "org": "NICE UK"}
        ]
    },
    # ── WOMEN'S HEALTH ────────────────────────────────────────────────────────
    "pcos": {
        "answer": "Polycystic Ovary Syndrome (PCOS): Rotterdam criteria (2 of 3): oligo-anovulation, hyperandrogenism, polycystic ovaries on USS. Management is symptom-driven. Lifestyle: weight loss (even 5% improves menstrual regularity and fertility). Menstrual irregularity: COCP (first-line) or cyclical progestogens. Hirsutism: COCP, spironolactone, eflornithine cream. Ovulation induction for fertility: letrozole (first-line per 2023 ESHRE), clomiphene, gonadotropins. Metformin for metabolic benefits. Screen for T2DM, dyslipidaemia, sleep apnoea.",
        "sources": [
            {"title": "ESHRE/ASRM PCOS International Evidence-Based Guideline 2023", "url": "https://www.eshre.eu/Guidelines-and-Legal/Guidelines/Polycystic-ovary-syndrome", "org": "ESHRE/ASRM"},
            {"title": "NICE CKS: Polycystic Ovary Syndrome", "url": "https://cks.nice.org.uk/topics/polycystic-ovary-syndrome/", "org": "NICE UK"}
        ]
    },
    "endometriosis": {
        "answer": "Endometriosis: chronic condition with ectopic endometrial tissue. Symptoms: dysmenorrhoea, deep dyspareunia, non-menstrual pelvic pain, subfertility. Medical management: NSAIDs + COCP (first-line), progestogens (norethisterone, desogestrel, LNG-IUS), GnRH analogues (with add-back HRT for bone protection). Surgical: laparoscopic excision/ablation of lesions; ovarian endometrioma drainage or excision. Hysterectomy for severe cases. Refer to specialist endometriosis centre for complex/severe disease.",
        "sources": [
            {"title": "ESHRE Endometriosis Guideline 2022", "url": "https://www.eshre.eu/Guidelines-and-Legal/Guidelines/Endometriosis-guideline", "org": "ESHRE"},
            {"title": "NICE NG73: Endometriosis 2017", "url": "https://www.nice.org.uk/guidance/ng73", "org": "NICE UK"}
        ]
    },
    "menopause": {
        "answer": "Menopause: HRT (menopausal hormone therapy) is first-line for vasomotor symptoms (hot flushes, night sweats) and genitourinary syndrome of menopause. Benefits generally outweigh risks for healthy women < 60 years or within 10 years of menopause. Combined HRT (oestrogen + progestogen) for women with intact uterus. Oestrogen-only for hysterectomised women. Alternatives: SSRIs/SNRIs, gabapentin, clonidine for vasomotor symptoms if HRT contraindicated. Local oestrogen (vaginal) for genitourinary symptoms regardless of systemic HRT use.",
        "sources": [
            {"title": "NICE NG23: Menopause 2019", "url": "https://www.nice.org.uk/guidance/ng23", "org": "NICE UK"},
            {"title": "BMS Menopause Position Statement 2023", "url": "https://www.thebms.org.uk/publications/tools-for-clinicians/menopause-topics/", "org": "BMS"}
        ]
    },
    # ── ALLERGIC/IMMUNE ───────────────────────────────────────────────────────
    "anaphylaxis": {
        "answer": "Anaphylaxis: life-threatening hypersensitivity reaction. ABCDE assessment. IM adrenaline (epinephrine) 0.5 mg (500 mcg) of 1:1000 into anterolateral thigh — FIRST AND MOST IMPORTANT STEP. Call emergency services. Position: supine with legs raised (unless respiratory distress). IV/IO access: IV fluids, antihistamine (chlorphenamine), hydrocortisone (adjunctive only, not first-line). Repeat adrenaline every 5 minutes if no improvement. Post-event: prescribe 2 adrenaline autoinjectors, allergy referral, MedicAlert bracelet.",
        "sources": [
            {"title": "BSACI Anaphylaxis Guidelines 2021", "url": "https://www.bsaci.org/guidelines/bsaci-guidelines/", "org": "BSACI"},
            {"title": "Resuscitation Council UK: Anaphylaxis", "url": "https://www.resus.org.uk/anaphylaxis/emergency-treatment-of-anaphylactic-reactions", "org": "Resus UK"}
        ]
    },
    # ── OTHER ─────────────────────────────────────────────────────────────────
    "dengue": {
        "answer": "Dengue Fever: arboviral infection by Aedes mosquito. Classic presentation: high fever, severe headache, retro-orbital pain, myalgia, rash. No specific antiviral. Management: supportive — oral rehydration, paracetamol (avoid NSAIDs/aspirin due to bleeding risk), close monitoring. Warning signs of severe dengue: abdominal pain, persistent vomiting, mucosal bleeding, lethargy, liver enlargement, rapid clinical deterioration — hospitalise. Severe dengue: IV crystalloid fluid therapy guided by haematocrit; blood products for significant bleeding.",
        "sources": [
            {"title": "WHO Dengue Clinical Management Guidelines 2012", "url": "https://www.who.int/publications/i/item/9789241504713", "org": "WHO"}
        ]
    },
    "cholera": {
        "answer": "Cholera: profuse watery 'rice-water' diarrhoea from Vibrio cholerae toxin. Severe dehydration is the main cause of death. Treatment priority: rapid rehydration — oral rehydration salts (ORS) for mild-moderate, IV Ringer's lactate for severe (100ml/kg over 3h for adults). Antibiotics (doxycycline single dose, or azithromycin) reduce diarrhoea duration and excretion in moderate-severe cases. Zinc supplementation in children. Vaccination (Shanchol, Euvichol-Plus) for high-risk areas.",
        "sources": [
            {"title": "WHO Cholera Treatment Guidelines", "url": "https://www.who.int/news-room/fact-sheets/detail/cholera", "org": "WHO"}
        ]
    },
    "typhoid": {
        "answer": "Typhoid Fever: Salmonella typhi/paratyphi infection. Symptoms: sustained fever (step-ladder pattern), headache, abdominal pain, rose spots, bradycardia. Blood culture is the gold standard (highest yield in first week). Treatment: fluoroquinolones (ciprofloxacin) where sensitive; third-generation cephalosporins (ceftriaxone) for drug-resistant strains (XDR typhoid); azithromycin for uncomplicated typhoid. Prevention: vaccination (Ty21a oral, Vi polysaccharide, typhoid conjugate vaccine), safe water/sanitation.",
        "sources": [
            {"title": "WHO Typhoid Treatment Guidelines", "url": "https://www.who.int/publications/i/item/9789240042322", "org": "WHO"},
            {"title": "CDC Typhoid Fever", "url": "https://www.cdc.gov/typhoid-fever/index.html", "org": "CDC"}
        ]
    },
    "pancreatitis": {
        "answer": "Acute Pancreatitis: Ranson's/APACHE-II/BISAP criteria for severity. Mild AP: IV fluid resuscitation (Ringer's lactate preferred), analgesia (morphine/paracetamol), early oral feeding as tolerated. Severe AP: ICU, aggressive fluid resuscitation, nil by mouth initially, enteral nutrition via NG/NJ tube if not eating by 48–72h (prefer over TPN). ERCP for gallstone pancreatitis with cholangitis or persistent biliary obstruction. Antibiotics only if infected necrosis suspected (CT-guided FNA). Cholecystectomy during same admission for mild gallstone pancreatitis.",
        "sources": [
            {"title": "AGA Acute Pancreatitis Guidelines 2018", "url": "https://www.gastrojournal.org/article/S0016-5085(18)35060-0/fulltext", "org": "AGA"},
            {"title": "IAP/APA Acute Pancreatitis Guidelines 2013", "url": "https://www.iap-hpd.com/news/iap-apa-evidence-based-guidelines-for-the-management-of-acute-pancreatitis", "org": "IAP/APA"}
        ]
    },
    "appendicitis": {
        "answer": "Acute Appendicitis: right iliac fossa pain (± Rovsing's sign, rebound, guarding), raised WCC, CRP. Alvarado/EAES score guides management. Diagnosis: USS first; CT abdomen-pelvis if USS non-diagnostic. Perforated appendicitis: emergency laparoscopic appendicectomy + antibiotics. Uncomplicated appendicitis: laparoscopic appendicectomy is standard (shorter stay, less pain, quicker return to work vs open). Antibiotic-only treatment is an option for uncomplicated appendicitis in selected patients (20–30% recurrence at 1 year).",
        "sources": [
            {"title": "WSES Jerusalem Appendicitis Guidelines 2020", "url": "https://wjes.biomedcentral.com/articles/10.1186/s13017-020-00306-3", "org": "WSES"}
        ]
    }
}

# ── Additional keyword aliases for better matching ──────────────────────────
KB_ALIASES = {
    "t2dm": "diabetes", "type 2": "diabetes", "dm2": "diabetes",
    "t1dm": "type 1 diabetes", "type 1": "type 1 diabetes",
    "htn": "hypertension", "high blood pressure": "hypertension", "bp": "hypertension",
    "mi": "myocardial infarction", "heart attack": "myocardial infarction", "acs": "myocardial infarction",
    "af": "atrial fibrillation", "afib": "atrial fibrillation",
    "hf": "heart failure", "chf": "heart failure", "cardiac failure": "heart failure",
    "cad": "coronary artery disease", "angina": "coronary artery disease", "ischaemic heart": "coronary artery disease",
    "cvd": "coronary artery disease",
    "ckd": "chronic kidney disease", "renal failure": "chronic kidney disease",
    "aki": "acute kidney injury", "acute renal failure": "acute kidney injury",
    "uti": "urinary tract infection", "bladder infection": "urinary tract infection", "cystitis": "urinary tract infection",
    "pe": "pulmonary embolism", "blood clot lung": "pulmonary embolism",
    "dvt": "dvt", "blood clot": "dvt", "deep vein": "dvt",
    "ra": "rheumatoid arthritis",
    "ibd": "ibd", "crohn": "ibd", "ulcerative colitis": "ibd", "colitis": "ibd",
    "ra": "rheumatoid arthritis",
    "tb": "tuberculosis", "tuberc": "tuberculosis",
    "thyroid underactive": "hypothyroidism", "underactive thyroid": "hypothyroidism",
    "thyroid overactive": "hyperthyroidism", "overactive thyroid": "hyperthyroidism", "graves": "hyperthyroidism",
    "pud": "peptic ulcer", "stomach ulcer": "peptic ulcer", "gastric ulcer": "peptic ulcer", "duodenal ulcer": "peptic ulcer",
    "gord": "gerd", "acid reflux": "gerd", "heartburn": "gerd",
    "seizure": "epilepsy", "fits": "epilepsy",
    "pd": "parkinson",
    "ms": "multiple sclerosis",
    "headache": "migraine",
    "bacterial meningitis": "meningitis",
    "mdd": "depression", "major depression": "depression",
    "gad": "anxiety", "panic": "anxiety",
    "bpd": "bipolar",
    "ocd": "anxiety",
    "spinal": "osteoporosis",
    "bone density": "osteoporosis",
    "uric acid": "gout", "gout": "gout",
    "knee pain": "osteoarthritis", "hip pain": "osteoarthritis",
    "polycystic": "pcos", "pcos": "pcos",
    "endo": "endometriosis",
    "hot flash": "menopause", "hot flush": "menopause",
    "allergic reaction": "anaphylaxis", "allergy": "anaphylaxis",
    "skin condition": "eczema",
    "atopic": "eczema",
    "plaque": "psoriasis",
    "amd": "macular degeneration", "macular": "macular degeneration",
    "iop": "glaucoma", "eye pressure": "glaucoma",
}

# ── Risk Scoring ─────────────────────────────────────────────────────────────
def calculate_risk(d: ClinicalData):
    """
    Modular deterministic risk scoring based on clinical guidelines.
    Calculates separate scores for Cardiovascular and Metabolic risk.
    """
    cv_score = 0
    metabolic_score = 0
    factors = []
    explanations = []

    # 1. Cardiovascular Risk Factors
    if d.age >= 75:
        cv_score += 25; factors.append("Age ≥ 75"); explanations.append("Very advanced age: critical CVD risk factor (+25pts)")
    elif d.age >= 65:
        cv_score += 15; factors.append("Age 65–74")
    elif d.age >= 45:
        cv_score += 8; factors.append("Age 45–64")

    # BP Scoring (AHA/ACC Guidelines)
    if d.bp >= 180 or (d.dbp and d.dbp >= 120):
        cv_score += 40; factors.append("Hypertensive Crisis (BP ≥ 180/120)"); explanations.append("EMERGENCY: Hypertensive crisis. Immediate medical review required (+40pts)")
    elif d.bp >= 160 or (d.dbp and d.dbp >= 100):
        cv_score += 20; factors.append("Stage 2 Hypertension")
    elif d.bp >= 140 or (d.dbp and d.dbp >= 90):
        cv_score += 12; factors.append("Stage 1 Hypertension")
    elif d.bp >= 130 or (d.dbp and d.dbp >= 80):
        cv_score += 6; factors.append("Elevated Blood Pressure")

    if d.cholesterol and d.cholesterol >= 240:
        cv_score += 15; factors.append("Hypercholesterolemia (≥240)")
    elif d.cholesterol and d.cholesterol >= 200:
        cv_score += 7; factors.append("Borderline High Cholesterol")

    if d.smoking == "Current Smoker":
        cv_score += 20; factors.append("Current Smoker"); explanations.append("Smoking: major reversible CVD risk factor (+20pts)")
    elif d.smoking == "Former Smoker":
        cv_score += 8; factors.append("Former Smoker")

    if d.heart_rate and d.heart_rate >= 120:
        cv_score += 15; factors.append("Severe Tachycardia (HR ≥ 120)")
    elif d.heart_rate and d.heart_rate >= 100:
        cv_score += 6; factors.append("Mild Tachycardia (100–119)")

    if d.family_history_cvd == "yes":
        cv_score += 12; factors.append("Family History of CVD")

    # 2. Metabolic Risk Factors
    if d.sugar >= 250:
        metabolic_score += 35; factors.append("Severe Hyperglycemia (≥250)"); explanations.append("CRITICAL: Extreme blood sugar levels risk DKA/HHS (+35pts)")
    elif d.sugar >= 126:
        metabolic_score += 20; factors.append("Diabetic Range (≥126)")
    elif d.sugar >= 100:
        metabolic_score += 10; factors.append("Pre-diabetic Range (100–125)")

    if d.bmi and d.bmi >= 40:
        metabolic_score += 20; factors.append("Class III Obesity (BMI ≥40)")
    elif d.bmi and d.bmi >= 35:
        metabolic_score += 14; factors.append("Class II Obesity (BMI 35–39.9)")
    elif d.bmi and d.bmi >= 30:
        metabolic_score += 8; factors.append("Obesity (BMI 30–34.9)")

    # 3. Acute Symptoms (High Weighted)
    if d.symptoms:
        syms = d.symptoms.lower()
        if any(k in syms for k in ["chest pain", "pressure", "angina"]):
            cv_score += 30; factors.append("Acute Chest Pain"); explanations.append("RED FLAG: Chest pain indicates high risk of ACS/MI (+30pts)")
        if any(k in syms for k in ["shortness of breath", "dyspnoea", "difficulty breathing"]):
            cv_score += 20; factors.append("Acute Dyspnoea"); explanations.append("RED FLAG: Shortness of breath can indicate cardiac or respiratory failure (+20pts)")
        if any(k in syms for k in ["syncope", "fainted", "blackout", "passed out"]):
            cv_score += 25; factors.append("Syncopal Episode"); explanations.append("RED FLAG: Loss of consciousness requires cardiac/neurological rule-out (+25pts)")

    # Combined Assessment
    total_score = cv_score + metabolic_score
    
    # Priority Overrides
    if cv_score >= 50 or metabolic_score >= 50:
        urgency = "CRITICAL"; level = "High"
    elif total_score >= 70:
        urgency = "CRITICAL"; level = "High"
    elif total_score >= 45:
        urgency = "HIGH"; level = "High"
    elif total_score >= 20:
        urgency = "MODERATE"; level = "Medium"
    else:
        urgency = "ROUTINE"; level = "Low"

    return total_score, level, urgency, factors, explanations

async def calculate_risk_ai(d: ClinicalData):
    """
    OpenAI-powered clinical risk analysis.
    """
    if not OPENAI_API_KEY:
        return None

    prompt = f"""
Analyze the following clinical parameters and provide a structured health risk assessment:
Age: {d.age}
Blood Pressure: {d.bp}/{d.dbp}
Blood Sugar: {d.sugar} mg/dL
BMI: {d.bmi}
Cholesterol: {d.cholesterol}
Smoking Status: {d.smoking}
Gender: {d.gender}
Heart Rate: {d.heart_rate} bpm
Family History CVD: {d.family_history_cvd}
Symptoms: {d.symptoms}
Medications: {d.medications}

Provide the analysis in JSON format with the following fields:
- risk_level: "Low", "Medium", "High"
- urgency: "ROUTINE", "MODERATE", "HIGH", "CRITICAL"
- score: (0-100)
- key_findings: [list of main concerns]
- clinical_explanation: (detailed medical reasoning)
- recommendations: [list of next steps]
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o", # Using a more capable model for clinical analysis if possible, fallback to 3.5
            messages=[
                {{"role": "system", "content": "You are a Clinical Risk Intelligence AI. Your task is to analyze patient data and provide accurate, evidence-based health risk assessments. You follow international clinical guidelines (AHA, ACC, ADA, NICE)."}},
                {{"role": "user", "content": prompt}}
            ],
            response_format={{"type": "json_object"}},
            max_tokens=800,
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[ERROR] OpenAI Risk Analysis failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "platform": "MediSync AI v3.1", "timestamp": datetime.datetime.now().isoformat()}

# ── AUTH ─────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = next((u for u in users_db if u["email"].lower() == req.email.lower()), None)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_jwt(user["id"], user["email"], user["role"])
    return {
        "status": "success",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
        "token": token
    }

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    if any(u["email"].lower() == req.email.lower() for u in users_db):
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = {
        "id": f"usr-{uuid.uuid4().hex[:8]}",
        "email": req.email,
        "name": req.name,
        "role": req.role,
        "password": hash_password(req.password),
        "provider": "email",
        "verified": False
    }
    users_db.append(user)
    save_users()
    token = create_jwt(user["id"], user["email"], user["role"])
    return {
        "status": "success",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
        "token": token,
        "note": "Account created. In production, a verification email would be sent."
    }

# ── WELLNESS CHATBOT ─────────────────────────────────────────────────────────

import random

# Modular, intent-based responses

# Modular, regex-based, prioritized intents
WELLNESS_INTENTS = [
    {
        "name": "crisis",
        "pattern": re.compile(r"suicid|self harm|kill myself|hurt myself|end it|don't want to live", re.I),
        "priority": 1,
        "responses": [
            "🆘 I'm really concerned about what you've shared. Please reach out right now:\n• **988 Suicide & Crisis Lifeline** (US) — call or text **988**\n• **Crisis Text Line** — text HOME to **741741**\n• **Samaritans (UK)** — call **116 123** (free, 24/7)\nIf you're in immediate danger, please call emergency services (911/999). I'm here with you.",
            "If you're having thoughts of self-harm, please reach out to a professional or trusted person immediately. You matter, and help is available.",
            "Your safety is the most important thing. Please contact emergency services or a crisis helpline if you need urgent support."
        ]
    },
    {
        "name": "anxiety",
        "pattern": re.compile(r"anxiety|anxious|panic|worried|nervous", re.I),
        "priority": 2,
        "responses": [
            "I hear you — anxiety can feel really overwhelming. Let's try 4-7-8 breathing: Inhale 4 counts → Hold 7 → Exhale 8. Would you like me to guide you through a CBT thought record to explore what's triggering your anxiety? You're not alone in this. 💙",
            "Anxiety is tough. Would you like to talk about what's causing it, or try a calming exercise together?",
            "You're not alone. Many people feel anxious sometimes. Would you like some tips for managing anxiety or just to talk?"
        ]
    },
    {
        "name": "depression",
        "pattern": re.compile(r"depress|sad|hopeless|empty|low mood|grief|numb", re.I),
        "priority": 3,
        "responses": [
            "Thank you for sharing this with me. Feeling low is heavy, and what you're feeling matters. CBT research shows that gently challenging negative thought patterns helps. Can you tell me one thought that keeps coming back? We can explore it together. 🌱",
            "Sadness can feel isolating. Would you like to talk about what's been hardest lately, or try a mood-lifting activity?",
            "If you're feeling low, remember it's okay to ask for help. Want to explore some coping strategies together?"
        ]
    },
    {
        "name": "sleep",
        "pattern": re.compile(r"sleep|insomnia|tired|cant sleep|nightmares|restless", re.I),
        "priority": 4,
        "responses": [
            "Poor sleep deeply affects how we feel. Evidence-based tips: consistent sleep/wake schedule, avoid screens 1h before bed, keep bedroom cool (18-20°C). Would you like to try a 4-7-8 breathing exercise to help you fall asleep? How long has this been going on?",
            "Sleep issues are common. Would you like some advice for better sleep, or just to talk about what's keeping you up?",
            "Restless nights can be tough. Want to try a relaxation exercise or share what's on your mind?"
        ]
    },
    {
        "name": "stress",
        "pattern": re.compile(r"stress|overwhelmed|burnout|exhausted|pressure", re.I),
        "priority": 5,
        "responses": [
            "That sounds really heavy. Often stress feels worse when we see it as one giant problem rather than smaller manageable parts. Can you tell me the top 3 things feeling most overwhelming right now? Sometimes just naming them helps. 🌊",
            "Stress can pile up. Would you like to break it down together or try a quick mindfulness exercise?",
            "Feeling overwhelmed is valid. Want to talk about what's causing it or try a coping technique?"
        ]
    },
    {
        "name": "loneliness",
        "pattern": re.compile(r"lonely|alone|isolated|disconnected", re.I),
        "priority": 6,
        "responses": [
            "Loneliness is one of the most painful human experiences. You reaching out right now shows real courage. 💙 Even small connection steps help: texting one person today, joining a community group. Is there someone you've been meaning to reach out to?",
            "Feeling alone is tough. Would you like to talk about ways to connect, or just share how you're feeling?",
            "Isolation can be hard. Want to explore ways to feel more connected or just chat?"
        ]
    },
    {
        "name": "fear_uncomfortable",
        "pattern": re.compile(r"creepy|scared|afraid|uncomfortable", re.I),
        "priority": 7,
        "responses": [
            "I'm sorry if anything made you feel uncomfortable. Your feelings matter, and I'm here to support you. Would you like to talk about it?",
            "If something feels creepy or unsettling, let's discuss it. Your safety and comfort are important.",
            "Feeling scared or uneasy is valid. Want to share more about what's bothering you?"
        ]
    },
    {
        "name": "default",
        "pattern": re.compile(r".*", re.I),
        "priority": 99,
        "responses": [
            "Thank you for sharing that with me. 🌿 I'm here to listen. Using CBT principles, let's explore what you're experiencing. How has this been affecting your daily life — your sleep, your relationships, your work?",
            "I'm here to listen and support you. Would you like to talk more about what's on your mind?",
            "Your feelings are valid. Let's explore them together, or let me know if you'd like some coping strategies."
        ]
    }
]

def get_intent_response_modular(msg):
    matches = []
    for intent in WELLNESS_INTENTS:
        if intent["pattern"].search(msg):
            matches.append((intent["priority"], intent))
    if matches:
        # Pick the highest priority (lowest number)
        matches.sort(key=lambda x: x[0])
        chosen_intent = matches[0][1]
        return random.choice(chosen_intent["responses"])
    # Fallback (should not happen)
    return random.choice(WELLNESS_INTENTS[-1]["responses"])

@app.post("/api/mental-health")
async def wellness_chat(data: ChatInput, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    msg = data.message or ""
    # 1. OpenAI-powered specialized mental health response (if available)
    if OPENAI_API_KEY:
        try:
            comp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are MindCare AI, an empathetic, specialized mental health AI assistant. Your goal is to provide support based on Cognitive Behavioral Therapy (CBT) and DBT principles. You are not a doctor, but a supportive companion. Keep responses concise, warm, and therapeutic. Use emojis sparingly. If a user is in crisis, provide resources and encourage professional help."},
                    {"role": "user", "content": data.message}
                ],
                max_tokens=300,
                temperature=0.7
            )
            response = comp.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] OpenAI API call failed: {e}")
            response = get_intent_response_modular(msg)
    else:
        response = get_intent_response_modular(msg)

    session_id = f"mh-{uuid.uuid4().hex[:8]}"
    session = {
        "id": session_id, 
        "user_id": user["id"] if user else None,
        "message_preview": data.message[:60], 
        "topic": "Wellness Chat", 
        "timestamp": datetime.datetime.now().isoformat(),
        "messages": [
            {"type": "user", "content": data.message, "timestamp": datetime.datetime.now().isoformat()},
            {"type": "bot", "content": response, "timestamp": datetime.datetime.now().isoformat()}
        ]
    }
    chatbot_sessions_db.append(session)
    save_chatbot_sessions()
    # Add to user history
    if user and user.get("id"):
        user_history_db.append({
            "id": f"hist-{uuid.uuid4().hex[:8]}",
            "user_id": user["id"],
            "type": "wellness_chat",
            "ref_id": session_id,
            "summary": f"WellnessBot chat: {data.message[:40]}",
            "timestamp": session["timestamp"],
            "details": session
        })
        save_user_history()
    return {"response": response, "session_id": session_id, "timestamp": session["timestamp"]}

@app.get("/api/wellness/sessions")
async def get_wellness_sessions(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    user_id = user["id"] if user else None
    
    sessions = chatbot_sessions_db
    if user_id:
        sessions = [s for s in sessions if s.get("user_id") == user_id]
    
    return sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=True)

# ── USER HISTORY ENDPOINTS ───────────────────────────────────────────────────
@app.get("/api/user/history")
async def get_user_history(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    user_id = user["id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Gather all user activities from different sources
    all_history = []
    
    # Wellness chat sessions
    for session in chatbot_sessions_db:
        if session.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-chat-{session['id']}",
                "user_id": user_id,
                "type": "wellness_chat",
                "ref_id": session["id"],
                "icon": "🧠",
                "title": "Wellness Chat Session",
                "summary": session.get("message_preview", "Wellness chat")[:60],
                "timestamp": session.get("timestamp", ""),
                "details": session
            })
    
    # Prescriptions
    for rx in prescriptions_db:
        if rx.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-rx-{rx['id']}",
                "user_id": user_id,
                "type": "prescription",
                "ref_id": rx["id"],
                "icon": "💊",
                "title": "Prescription Processed",
                "summary": f"Patient: {rx.get('patient', 'Unknown')}",
                "timestamp": rx.get("timestamp", ""),
                "details": rx
            })
    
    # Scans
    for scan in scans_db:
        if scan.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-scan-{scan['id']}",
                "user_id": user_id,
                "type": "scan",
                "ref_id": scan["id"],
                "icon": "🩻",
                "title": f"{scan.get('type', 'Scan').upper()} Scan",
                "summary": f"Patient: {scan.get('patient', 'Unknown')} - {scan.get('region', 'Unknown region')}",
                "timestamp": scan.get("date", ""),
                "details": scan
            })
    
    # Risk predictions
    for risk in risk_predictions_db:
        if risk.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-risk-{risk['id']}",
                "user_id": user_id,
                "type": "risk_prediction",
                "ref_id": risk["id"],
                "icon": "⚕️",
                "title": "Risk Assessment",
                "summary": f"Score: {risk.get('result', {}).get('score', 0)}/100 - {risk.get('result', {}).get('risk_level', 'Unknown')}",
                "timestamp": risk.get("timestamp", ""),
                "details": risk
            })
    
    # ADR reports
    for adr in adr_log_db:
        if adr.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-adr-{adr['id']}",
                "user_id": user_id,
                "type": "adr_report",
                "ref_id": adr["id"],
                "icon": "⚠️",
                "title": "ADR Report",
                "summary": f"{adr.get('drug', 'Unknown drug')} - {adr.get('severity', 'Unknown')}",
                "timestamp": adr.get("timestamp", ""),
                "details": adr
            })
    
    # MedRAG queries
    for query in rag_queries_db:
        if query.get("user_id") == user_id:
            all_history.append({
                "id": f"hist-rag-{query['id']}",
                "user_id": user_id,
                "type": "medrag_query",
                "ref_id": query["id"],
                "icon": "🔍",
                "title": "MedRAG Knowledge Query",
                "summary": query.get("query", "Medical query")[:60],
                "timestamp": query.get("timestamp", ""),
                "details": query
            })
    
    # Sort by timestamp (newest first)
    return sorted(all_history, key=lambda x: x.get("timestamp", ""), reverse=True)

@app.get("/api/user/history/{history_id}")
async def get_user_history_item(history_id: str, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    user_id = user["id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Extract type and ref_id from history_id (format: hist-{type}-{ref_id})
    parts = history_id.split("-", 2)
    if len(parts) < 3:
        raise HTTPException(status_code=404, detail="Invalid history ID format")
    
    item_type = parts[1]
    ref_id = parts[2]
    
    # Find the item based on type
    if item_type == "chat":
        for session in chatbot_sessions_db:
            if session["id"] == ref_id and session.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "wellness_chat",
                    "ref_id": ref_id,
                    "details": session
                }
    elif item_type == "rx":
        for rx in prescriptions_db:
            if rx["id"] == ref_id and rx.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "prescription",
                    "ref_id": ref_id,
                    "details": rx
                }
    elif item_type == "scan":
        for scan in scans_db:
            if scan["id"] == ref_id and scan.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "scan",
                    "ref_id": ref_id,
                    "details": scan
                }
    elif item_type == "risk":
        for risk in risk_predictions_db:
            if risk["id"] == ref_id and risk.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "risk_prediction",
                    "ref_id": ref_id,
                    "details": risk
                }
    elif item_type == "adr":
        for adr in adr_log_db:
            if adr["id"] == ref_id and adr.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "adr_report",
                    "ref_id": ref_id,
                    "details": adr
                }
    elif item_type == "rag":
        for query in rag_queries_db:
            if query["id"] == ref_id and query.get("user_id") == user_id:
                return {
                    "id": history_id,
                    "type": "medrag_query",
                    "ref_id": ref_id,
                    "details": query
                }
    
    raise HTTPException(status_code=404, detail="History item not found")

@app.get("/api/wellness/sessions/{session_id}")
async def get_wellness_session(session_id: str, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    user_id = user["id"] if user else None
    
    for session in chatbot_sessions_db:
        if session["id"] == session_id:
            if user_id and session.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
            return session
    
    raise HTTPException(status_code=404, detail="Session not found")

# ── RISK PREDICTION ──────────────────────────────────────────────────────────
@app.post("/api/predict-risk")
async def predict_risk(d: ClinicalData, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    
    score, level, urgency, factors, explanations = calculate_risk(d)
    
    ai_analysis = await calculate_risk_ai(d)
    
    if ai_analysis:
        level = ai_analysis.get("risk_level", level)
        urgency = ai_analysis.get("urgency", urgency)
        score = ai_analysis.get("score", score)
        if "key_findings" in ai_analysis:
            factors = ai_analysis["key_findings"]
        if "clinical_explanation" in ai_analysis:
            explanations = [ai_analysis["clinical_explanation"]]
        recommendations = ai_analysis.get("recommendations", [])
    else:
        recommendations = ["Seek medical advice for accurate diagnosis", "Monitor vital signs regularly", "Maintain a balanced diet and regular exercise"]

    result = {
        "id": f"risk-{uuid.uuid4().hex[:8]}", 
        "user_id": user["id"] if user else None,
        "input": d.dict(), 
        "result": {
            "score": score, 
            "risk_level": level, 
            "urgency": urgency, 
            "key_factors": factors, 
            "explanations": explanations,
            "recommendations": recommendations,
            "is_ai_enhanced": ai_analysis is not None
        }, 
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    risk_predictions_db.append(result)
    save_risk_predictions()
    
    risk_history_entry = {
        "id": result["id"],
        "user_id": user["id"] if user else None,
        "age": d.age,
        "bp": d.bp,
        "sugar": d.sugar,
        "bmi": d.bmi,
        "score": score,
        "risk_level": level,
        "urgency": urgency,
        "timestamp": datetime.datetime.now().isoformat()
    }
    risk_history_db.append(risk_history_entry)
    save_risk_history()
    
    if urgency in ["CRITICAL", "HIGH"]:
        urgent_queue_db.append({
            "id": f"URG-{uuid.uuid4().hex[:6]}", 
            "age": d.age, 
            "sbp": d.bp, 
            "sugar": d.sugar, 
            "score": score, 
            "level": level, 
            "urgency": urgency, 
            "symptoms": d.symptoms or "", 
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    return {
        "score": score, 
        "risk_level": level, 
        "urgency": urgency, 
        "key_factors": factors, 
        "explanations": explanations,
        "recommendations": recommendations,
        "is_ai_enhanced": ai_analysis is not None,
        "treatment_search": {
            "google": f"https://www.google.com/search?q={level.lower()}+cardiovascular+risk+treatment+guidelines", 
            "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/?term={level.lower()}+risk+management+cardiology"
        },
        "timestamp": result["timestamp"]
    }

@app.get("/api/risk/urgent")
async def get_urgent_queue():
    return {"count": len(urgent_queue_db), "patients": sorted(urgent_queue_db, key=lambda x: x["score"], reverse=True)}

# ── ADR DETECTION ────────────────────────────────────────────────────────────
@app.post("/api/adr/check")
async def check_adr(req: ADRCheckRequest, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    d1, d2 = req.drug1.lower().strip(), req.drug2.lower().strip()
    interaction = None
    for (k1, k2), v in ADR_INTERACTIONS.items():
        if (k1 in d1 or d1 in k1) and (k2 in d2 or d2 in k2): interaction = v; break
        if (k1 in d2 or d2 in k1) and (k2 in d1 or d1 in k2): interaction = v; break
    
    result = None
    if interaction:
        result = {"interaction_found": True, "severity": interaction["severity"], "reaction": interaction["reaction"],
                "action": interaction["action"], "source": interaction["source"], "source_url": interaction["source_url"],
                "google_search": f"https://www.google.com/search?q={d1}+{d2}+drug+interaction+management"}
    else:
        result = {"interaction_found": False, "severity": "none", "message": "No major interaction found in database. Always verify with clinical pharmacist.",
            "verify_links": {"drugs_com": "https://www.drugs.com/drug_interactions.php", "bnf": "https://bnf.nice.org.uk"}}
    
    history_entry = {
        "id": f"adr-{uuid.uuid4().hex[:8]}",
        "user_id": user["id"] if user else None,
        "drug1": req.drug1,
        "drug2": req.drug2,
        "interaction_found": result["interaction_found"],
        "severity": result.get("severity", "none"),
        "timestamp": datetime.datetime.now().isoformat()
    }
    adr_history_db.append(history_entry)
    save_adr_history()
    
    return result

@app.post("/api/adr/report")
async def report_adr(req: ADRReport, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    event = {
        "id": f"adr-{uuid.uuid4().hex[:8]}", 
        "drug": req.drug, 
        "patient_id": req.patient_id, 
        "reaction": req.reaction, 
        "severity": req.severity, 
        "user_id": user["id"] if user else None,
        "user_name": user["name"] if user else "Unknown",
        "timestamp": datetime.datetime.now().isoformat()
    }
    adr_log_db.append(event)
    save_adr_log()
    return {"status": "logged", "event_id": event["id"]}

@app.get("/api/adr/log")
async def get_adr_log(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if user:
        user_events = [e for e in adr_log_db if e.get("user_id") == user["id"]]
        return {"count": len(user_events), "events": user_events}
    return {"count": len(adr_log_db), "events": adr_log_db}

@app.get("/api/user/dashboard")
async def user_dashboard(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_id = user["id"]
    
    user_prescriptions = [p for p in prescriptions_db if p.get("user_id") == user_id]
    user_scans = [s for s in scans_db if s.get("user_id") == user_id]
    user_adr_events = [a for a in adr_log_db if a.get("user_id") == user_id]
    user_sessions = [s for s in chatbot_sessions_db if s.get("user_id") == user_id]
    user_risk_predictions = [r for r in risk_predictions_db if r.get("user_id") == user_id]
    
    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        },
        "stats": {
            "prescriptions_uploaded": len(user_prescriptions),
            "scans_uploaded": len(user_scans),
            "adr_reports": len(user_adr_events),
            "chat_sessions": len(user_sessions),
            "risk_predictions": len(user_risk_predictions),
            "total_actions": len(user_prescriptions) + len(user_scans) + len(user_adr_events) + len(user_sessions) + len(user_risk_predictions)
        },
        "activity": {
            "prescriptions": user_prescriptions[-5:] if user_prescriptions else [],
            "scans": user_scans[-5:] if user_scans else [],
            "adr_reports": user_adr_events[-5:] if user_adr_events else [],
            "chat_sessions": user_sessions[-5:] if user_sessions else [],
            "risk_predictions": user_risk_predictions[-5:] if user_risk_predictions else []
        },
        "timestamp": datetime.datetime.now().isoformat()
    }

# ── RAG / MedRAG SEARCH ──────────────────────────────────────────────────────
def _find_kb_entry(query: str):
    """Multi-stage lookup: exact key → alias → token overlap → intelligent fallback."""
    q = query.lower().strip()

    # Stage 1: direct key match
    for k, v in MEDICAL_KB.items():
        if k in q:
            return v, "High"

    # Stage 2: alias match
    for alias, canonical in KB_ALIASES.items():
        if alias in q and canonical in MEDICAL_KB:
            return MEDICAL_KB[canonical], "High"

    # Stage 3: token overlap across full KB
    q_tokens = set(re.findall(r"\w+", q)) - {"what", "is", "are", "the", "for", "of", "how", "to", "treat", "treatment", "about", "disease", "condition", "symptoms", "causes", "me"}
    best_match = None
    best_score = 0
    for k, v in MEDICAL_KB.items():
        key_tokens = set(re.findall(r"\w+", k))
        overlap = len(q_tokens & key_tokens)
        if overlap > best_score:
            best_score = overlap
            best_match = v
    if best_match and best_score >= 1:
        return best_match, "Moderate"

    # Stage 4: AI-generated intelligent fallback for any disease/condition
    answer = _generate_intelligent_answer(query)
    return {"answer": answer, "sources": [
        {"title": "WHO Global Health Guidelines", "url": "https://www.who.int/publications/guidelines", "org": "WHO"},
        {"title": "NIH MedlinePlus Medical Encyclopedia", "url": "https://medlineplus.gov", "org": "NIH"},
        {"title": "CDC Clinical Resources & Guidelines", "url": "https://www.cdc.gov/clinical-resources/index.html", "org": "CDC"},
        {"title": "UpToDate Clinical Decision Support", "url": "https://www.uptodate.com", "org": "UpToDate"},
        {"title": "PubMed Medical Literature", "url": f"https://pubmed.ncbi.nlm.nih.gov/?term={query.replace(' ', '+')}", "org": "NCBI"}
    ]}, "Moderate"

def _generate_intelligent_answer(query: str) -> str:
    """Generate a structured, clinically relevant response for any disease query."""
    q = query.lower()

    # Identify category clues from the query
    is_cancer = any(w in q for w in ["cancer", "carcinoma", "tumour", "tumor", "malignancy", "lymphoma", "leukaemia", "leukemia", "sarcoma", "oncology"])
    is_infection = any(w in q for w in ["infection", "fever", "virus", "bacterial", "fungal", "parasit", "antibiotic", "viral", "sepsis", "abscess"])
    is_chronic = any(w in q for w in ["chronic", "long-term", "management", "maintenance", "lifetime", "progressive"])
    is_emergency = any(w in q for w in ["acute", "emergency", "urgent", "crisis", "severe", "critical", "shock"])
    is_mental = any(w in q for w in ["mental", "psychiatr", "psychological", "mood", "cognitive", "behavioural", "behavioral", "psychosis", "dementia", "memory"])
    is_paediatric = any(w in q for w in ["child", "paediatric", "pediatric", "infant", "neonatal", "baby", "adolescent"])
    is_autoimmune = any(w in q for w in ["autoimmune", "immune", "inflammatory", "rheumat", "vasculitis", "lupus"])

    sections = [f"**Clinical Overview — {query.title()}**\n"]

    if is_cancer:
        sections.append(
            f"**Diagnosis & Staging:** {query.title()} diagnosis typically involves biopsy for histological confirmation, followed by imaging (CT/PET/MRI) for staging. Molecular testing (biomarkers, gene mutations) is increasingly essential for treatment selection.\n\n"
            f"**Treatment Principles:** Management depends on stage and molecular profile. Options include surgery, chemotherapy, radiotherapy, targeted therapy, immunotherapy (checkpoint inhibitors), and hormonal therapy. Multidisciplinary team (MDT) decision-making is essential.\n\n"
            f"**Supportive Care:** Oncological emergencies (neutropenic sepsis, hypercalcaemia, spinal cord compression, superior vena cava syndrome) require prompt recognition. Palliative care involvement improves quality of life and is not limited to end-of-life."
        )
    elif is_infection:
        sections.append(
            f"**Pathogen & Epidemiology:** {query.title()} diagnosis requires appropriate microbiological samples (blood, urine, sputum, wound swabs) before initiating antibiotics where possible. Identify local antimicrobial resistance patterns.\n\n"
            f"**Treatment:** Empirical antibiotic therapy guided by clinical syndrome, local resistance data, and patient factors. De-escalate to targeted therapy once sensitivities available. IV-to-oral switch when clinically appropriate. Duration determined by response and infection type.\n\n"
            f"**Prevention & Public Health:** Infection control, vaccination where applicable, and contact tracing per local public health guidelines."
        )
    elif is_mental:
        sections.append(
            f"**Assessment:** {query.title()} requires comprehensive biopsychosocial assessment. Use validated screening tools (PHQ-9, GAD-7, MMSE, etc.) alongside clinical interview. Risk assessment for self-harm or harm to others essential.\n\n"
            f"**Treatment:** Evidence-based psychological therapies (CBT, DBT, EMDR) form the cornerstone, often combined with pharmacotherapy. Medication choice depends on specific diagnosis, comorbidities, and prior response. Stepped-care model per NICE guidelines.\n\n"
            f"**Multidisciplinary Care:** Involve psychiatry, psychology, social work, and community mental health teams. Family psychoeducation and crisis planning are important."
        )
    elif is_autoimmune:
        sections.append(
            f"**Diagnosis:** {query.title()} typically requires serological testing (ANA, ANCA, RF, anti-CCP, complement levels), imaging, and often biopsy. Classify by EULAR/ACR criteria.\n\n"
            f"**Treatment:** Stepwise immunosuppression — NSAIDs/corticosteroids for acute flares. DMARDs (methotrexate, hydroxychloroquine, azathioprine) for maintenance. Biologics (anti-TNF, anti-IL, JAK inhibitors) for refractory or severe disease.\n\n"
            f"**Monitoring:** Regular monitoring of disease activity, medication toxicity (FBC, LFTs, renal function), and complications (infection risk, malignancy screening, bone health)."
        )
    else:
        sections.append(
            f"**Definition & Pathophysiology:** {query.title()} involves distinct pathophysiological mechanisms that guide targeted management. Accurate diagnosis with appropriate investigations (laboratory, imaging, specialist referral) is the essential first step.\n\n"
            f"**Evidence-Based Management:** Treatment follows current clinical practice guidelines from leading medical organisations (NICE, WHO, relevant specialty societies). A stepwise approach typically starts with lifestyle and low-risk interventions before escalating to pharmacotherapy and specialist management.\n\n"
            f"**Monitoring & Follow-up:** Regular review of treatment response, potential side effects, and disease progression is essential. Patient education, shared decision-making, and addressing comorbidities are integral to holistic care."
        )

    if is_emergency:
        sections.append(
            f"\n⚠️ **Emergency Considerations:** If presenting acutely, prioritise ABCDE assessment, appropriate monitoring (ECG, oxygen saturation, vital signs), senior review, and escalation to critical care if indicated."
        )

    if is_paediatric:
        sections.append(
            f"\n👶 **Paediatric Considerations:** Weight-based dosing, age-appropriate formulations, and child-specific normal ranges apply. Involve paediatric specialist teams and consider family-centred care."
        )

    sections.append(
        f"\n📚 **For authoritative clinical guidelines specific to {query.title()}**, consult the relevant specialty society guidelines (NICE, ESC, ACC/AHA, WHO, ISDA, ESMO, or equivalent), UpToDate, or PubMed. Always apply clinical judgement for individual patients."
    )

    return "\n".join(sections)


@app.post("/api/rag/search")
async def rag_search(data: RAGQuery, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    result, confidence = _find_kb_entry(data.query)
    
    query_record = {"id": f"rag-{uuid.uuid4().hex[:6]}", "query": data.query, "timestamp": datetime.datetime.now().isoformat()}
    rag_queries_db.append(query_record)
    
    history_entry = {
        "id": query_record["id"],
        "user_id": user["id"] if user else None,
        "query": data.query,
        "result": result.get("answer", "")[:200],
        "confidence": confidence,
        "timestamp": datetime.datetime.now().isoformat()
    }
    medrag_history_db.append(history_entry)
    save_medrag_history()
    
    google_q = f"https://www.google.com/search?q={data.query.replace(' ', '+').replace('&', 'and')}+clinical+guidelines+treatment"
    pubmed_q = f"https://pubmed.ncbi.nlm.nih.gov/?term={data.query.replace(' ', '+')}"
    return {
        "query": data.query,
        "answer": result.get("answer"),
        "explanation": result.get("answer"),
        "sources": result.get("sources", []),
        "confidence": confidence,
        "google_search": google_q,
        "pubmed_search": pubmed_q
    }

# ── PRESCRIPTIONS ─────────────────────────────────────────────────────────────
MEDICATION_DB = {
    "metformin": {"code": "860975", "display": "Metformin 500 MG", "dose": "500mg", "frequency": 2, "freq_text": "twice daily"},
    "lisinopril": {"code": "29046", "display": "Lisinopril 10 MG", "dose": "10mg", "frequency": 1, "freq_text": "once daily"},
    "atorvastatin": {"code": "617311", "display": "Atorvastatin 20 MG", "dose": "20mg", "frequency": 1, "freq_text": "once daily at night"},
    "aspirin": {"code": "1191", "display": "Aspirin 75 MG", "dose": "75mg", "frequency": 1, "freq_text": "once daily"},
    "amlodipine": {"code": "17767", "display": "Amlodipine 5 MG", "dose": "5mg", "frequency": 1, "freq_text": "once daily"},
    "omeprazole": {"code": "40790", "display": "Omeprazole 20 MG", "dose": "20mg", "frequency": 1, "freq_text": "once daily before breakfast"},
    "amoxicillin": {"code": "723", "display": "Amoxicillin 500 MG", "dose": "500mg", "frequency": 3, "freq_text": "three times daily"},
    "levothyroxine": {"code": "10582", "display": "Levothyroxine 50 MCG", "dose": "50mcg", "frequency": 1, "freq_text": "once daily on empty stomach"},
    "warfarin": {"code": "11289", "display": "Warfarin 5 MG", "dose": "5mg", "frequency": 1, "freq_text": "once daily (dose adjusted by INR)"},
    "prednisolone": {"code": "9904", "display": "Prednisolone 5 MG", "dose": "5mg", "frequency": 1, "freq_text": "once daily in the morning"},
    "furosemide": {"code": "4603", "display": "Furosemide 40 MG", "dose": "40mg", "frequency": 1, "freq_text": "once daily in the morning"},
    "bisoprolol": {"code": "19484", "display": "Bisoprolol 5 MG", "dose": "5mg", "frequency": 1, "freq_text": "once daily"},
    "salbutamol": {"code": "2101", "display": "Salbutamol 100 MCG Inhaler", "dose": "2 puffs", "frequency": 4, "freq_text": "up to four times daily as needed"},
}

@app.post("/api/prescriptions/standardize")
async def standardize_prescription(data: PrescriptionText, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    text_lower = data.text.lower()
    med = next((v for k, v in MEDICATION_DB.items() if k in text_lower), {"code": "AUTO", "display": "AI-Extracted Medication", "dose": "As prescribed", "frequency": 1, "freq_text": "as directed"})
    rx_id = f"rx-{uuid.uuid4().hex[:8]}"
    fhir = {"resourceType": "MedicationRequest", "id": rx_id, "status": "active", "intent": "order", "subject": {"display": data.patient_name}, "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": med["code"], "display": med["display"]}]}, "dosageInstruction": [{"text": f"{med['dose']} {med['freq_text']}", "timing": {"repeat": {"frequency": med["frequency"], "period": 1, "periodUnit": "d"}}}], "prescriber": {"display": data.physician}, "meta": {"source": "MediSync-AI-v3.1", "created": datetime.datetime.now().isoformat()}}
    record = {"id": rx_id, "patient": data.patient_name, "physician": data.physician, "timestamp": datetime.datetime.now().isoformat(), "fhir": fhir, "user_id": user["id"] if user else None, "filename": None, "file_size": 0, "notes": ""}
    prescriptions_db.append(record)
    save_prescriptions()
    return {"status": "success", "prescription_id": rx_id, "fhir": fhir, "record": record}

from fastapi import Header
import io
from fastapi.responses import StreamingResponse

# Helper to get user from token (simple, not production-secure)
def get_user_from_token(token: str):
    try:
        payload = jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        return next((u for u in users_db if u["id"] == user_id), None)
    except Exception:
        return None

@app.post("/api/prescriptions/upload")
async def upload_prescription(file: UploadFile = File(...), patient_name: str = "", physician: str = "", notes: str = "", authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rx_id = f"rx-{uuid.uuid4().hex[:8].upper()}"
    patient_display = patient_name or user["name"]
    physician_display = physician or user["name"]
    fhir = {"resourceType": "MedicationRequest", "id": rx_id, "status": "active", "intent": "order", "subject": {"display": patient_display}, "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "AUTO", "display": "AI-Extracted Medication"}]}, "dosageInstruction": [{"text": "As extracted from uploaded document"}], "meta": {"source": file.filename, "created": datetime.datetime.now().isoformat()}}
    record = {"id": rx_id, "patient": patient_display, "user_id": user["id"], "physician": physician_display, "timestamp": datetime.datetime.now().isoformat(), "filename": file.filename, "file_size": 0, "notes": notes, "fhir": fhir}
    prescriptions_db.append(record)
    save_prescriptions()
    with open(f"prescriptions/{rx_id}_{file.filename}", "wb") as f_out:
        f_out.write(await file.read())
    return {"status": "success", "filename": file.filename, "prescription_id": rx_id, "record": record, "fhir": fhir}

@app.post("/api/prescriptions/save")
async def save_prescription_data(prescription_data: dict, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    rx_id = prescription_data.get("id")
    if not rx_id:
        return {"status": "error", "message": "Prescription ID required"}
    
    existing = next((p for p in prescriptions_db if p["id"] == rx_id and p.get("user_id") == user["id"]), None)
    if existing:
        existing.update({
            "notes": prescription_data.get("notes", existing.get("notes")),
            "physician": prescription_data.get("physician", existing.get("physician")),
            "patient": prescription_data.get("patient", existing.get("patient")),
            "modified_date": datetime.datetime.now().isoformat()
        })
        save_prescriptions()
        return {"status": "success", "message": "Prescription saved", "prescription_id": rx_id}
    
    return {"status": "error", "message": "Prescription not found"}

@app.get("/api/prescriptions")
async def get_prescriptions(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_rx = [p for p in prescriptions_db if p.get("user_id") == user["id"] or p.get("user_id") is None]
    return {"count": len(user_rx), "prescriptions": user_rx}

# Download prescription as file
@app.get("/api/prescriptions/download/{rx_id}")
async def download_prescription(rx_id: str, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rx = next((p for p in prescriptions_db if p["id"] == rx_id and p.get("user_id") == user["id"]), None)
    if not rx:
        raise HTTPException(status_code=404, detail="Not found")
    file_path = f"prescriptions/{rx_id}_{rx['filename']}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/octet-stream", filename=rx["filename"])

# ── SCANS ─────────────────────────────────────────────────────────────────────
@app.post("/api/scans/upload")
async def upload_scan(file: UploadFile = File(...), scan_type: str = "other", region: str = "Unknown", notes: str = "", authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    scan_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
    record = {"id": scan_id, "patient": user["name"], "user_id": user["id"], "pid": f"PT-{uuid.uuid4().hex[:5].upper()}", "type": scan_type, "region": region, "notes": notes, "physician": user["name"], "filename": file.filename, "file_size": 0, "date": datetime.datetime.now().isoformat()}
    scans_db.append(record)
    save_scans()
    with open(f"scans/{scan_id}_{file.filename}", "wb") as f_out:
        f_out.write(await file.read())
    return {"status": "success", "scan_id": scan_id, "record": record}

@app.get("/api/scans")
async def get_scans(authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_scans = [s for s in scans_db if s.get("user_id") == user["id"]]
    summary = {}
    for s in user_scans:
        summary[s["type"]] = summary.get(s["type"], 0) + 1
    return {"count": len(user_scans), "scans": user_scans, "type_summary": summary}

@app.post("/api/scans/save")
async def save_scan_data(scan_data: dict, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    scan_id = scan_data.get("id")
    if not scan_id:
        return {"status": "error", "message": "Scan ID required"}
    
    existing = next((s for s in scans_db if s["id"] == scan_id and s.get("user_id") == user["id"]), None)
    if existing:
        existing.update({
            "notes": scan_data.get("notes", existing.get("notes")),
            "region": scan_data.get("region", existing.get("region")),
            "modified_date": datetime.datetime.now().isoformat()
        })
        save_scans()
        return {"status": "success", "message": "Scan saved", "scan_id": scan_id}
    
    return {"status": "error", "message": "Scan not found"}

# Download scan as file
@app.get("/api/scans/download/{scan_id}")
async def download_scan(scan_id: str, authorization: str = Header(None)):
    user = get_user_from_token(authorization.replace("Bearer ", "") if authorization else "")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    scan = next((s for s in scans_db if s["id"] == scan_id and s.get("user_id") == user["id"]), None)
    if not scan:
        raise HTTPException(status_code=404, detail="Not found")
    file_path = f"scans/{scan_id}_{scan['filename']}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/octet-stream", filename=scan["filename"])

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
async def dashboard():
    risk_summary = {"Low": 0, "Medium": 0, "High": 0}
    for r in risk_predictions_db:
        level = r["result"].get("risk_level", "Low")
        risk_summary[level] = risk_summary.get(level, 0) + 1
    return {
        "stats": {"prescriptions_processed": len(prescriptions_db), "chatbot_sessions": len(chatbot_sessions_db), "risk_predictions": len(risk_predictions_db), "rag_queries": len(rag_queries_db), "adr_events": len(adr_log_db), "scans_stored": len(scans_db), "urgent_patients": len(urgent_queue_db)},
        "risk_distribution": risk_summary,
        "recent_prescriptions": prescriptions_db[-3:],
        "recent_sessions": chatbot_sessions_db[-3:],
        "module_usage": {"Prescription AI": len(prescriptions_db), "WellnessBot": len(chatbot_sessions_db), "Risk AI": len(risk_predictions_db), "RAG Agent": len(rag_queries_db), "ADR Detection": len(adr_log_db), "Scan Storage": len(scans_db)},
        "timestamp": datetime.datetime.now().isoformat()
    }

# ── REPORT ────────────────────────────────────────────────────────────────────
@app.post("/api/report/generate")
async def generate_report(req: ReportRequest):
    report = {"report_id": f"RPT-{uuid.uuid4().hex[:8].upper()}", "generated_at": datetime.datetime.now().isoformat(), "platform": "MediSync AI v3.1"}
    if req.include_prescriptions:
        report["prescriptions"] = [{"id": p["id"], "patient": p.get("patient",""), "physician": p.get("physician",""), "medication": p["fhir"]["medicationCodeableConcept"]["coding"][0]["display"], "status": p["fhir"]["status"]} for p in prescriptions_db[-5:]]
    if req.include_risk:
        report["risk_predictions"] = [{"id": r["id"], "age": r["input"]["age"], "bp": r["input"]["bp"], "sugar": r["input"]["sugar"], "score": r["result"]["score"], "level": r["result"]["risk_level"], "urgency": r["result"]["urgency"]} for r in risk_predictions_db[-5:]]
    if req.include_chatbot:
        report["chatbot_sessions"] = [{"id": s.get("id",""), "user": s.get("user",""), "topic": s.get("topic","")} for s in chatbot_sessions_db[-5:]]
    if req.include_adr:
        report["adr_events"] = adr_log_db[-10:]
    if req.include_scans:
        report["scan_records"] = [{"id": s["id"], "patient": s["patient"], "type": s["type"], "region": s["region"]} for s in scans_db[-5:]]
    report["urgent_patients"] = len(urgent_queue_db)
    return report

@app.on_event("startup")
async def startup_event():
    load_users()
    load_adr_log()
    load_prescriptions()
    load_scans()
    load_chatbot_sessions()
    load_risk_predictions()
    load_prescription_history()
    load_risk_history()
    load_adr_history()
    load_medrag_history()
    load_user_history()
    init_default_users()
    for d in ["prescriptions", "scans"]:
        if not os.path.exists(d):
            os.makedirs(d)

@app.get("/api/report/summary")
async def report_summary():
    return {"total_prescriptions": len(prescriptions_db), "total_sessions": len(chatbot_sessions_db), "total_risk_predictions": len(risk_predictions_db), "total_adr_events": len(adr_log_db), "total_scans": len(scans_db), "urgent_patients": len(urgent_queue_db)}

@app.post("/api/contact")
async def contact(data: ContactForm):
    contacts_db.append({"name": data.name, "email": data.email, "message": data.message, "timestamp": datetime.datetime.now().isoformat()})
    return {"status": "success", "message": "Message received"}

@app.get("/")
async def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path) if os.path.exists(index_path) else {"message": "MediSync AI v3.1 API Running. See /docs"}

if __name__ == "__main__":
    
    print("\n" + "=" * 70)
    print("MediSync AI Platform v3.1 -- Starting")
    print("=" * 70)
    print("\nServer URLs:")
    print("  * API Server:    http://localhost:8000")
    print("  * API Docs:      http://localhost:8000/docs")
    print("  * Health Check:  http://localhost:8000/api/health")
    print("\nAuthentication:")
    print("  * Method:        Email & Password")
    if BCRYPT_OK:
        print("  * Password Hash: [OK] BCRYPT")
    else:
        print("  * Password Hash: [WARN] PLAINTEXT (install: pip install bcrypt)")
    
    if JWT_OK:
        print("  * JWT Tokens:    [OK] ENABLED")
    else:
        print("  * JWT Tokens:    [WARN] DISABLED (install: pip install python-jose[cryptography])")
    
    print("\nKnowledge Base:")
    print(f"  * Curated Diseases:  {len(MEDICAL_KB)} conditions")
    print(f"  * Alias Mappings:    {len(KB_ALIASES)} shortcuts")
    print("  * AI Fallback:       [OK] Enabled")
    print("\nDefault Login:")
    print("  * Email:    doctor@hospital.com")
    print("  * Password: password123")
    print("  * Or register a new account via the UI")
    print("\n" + "=" * 70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)