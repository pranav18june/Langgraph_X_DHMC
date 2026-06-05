import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="DHMC Python Backend API", version="1.0.0")

# Enable CORS for the local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_dhmc_key_change_in_prod")
if not os.getenv("JWT_SECRET"):
    logger.warning(
        "JWT_SECRET is not set — using insecure default. "
        "Set JWT_SECRET in your environment for production."
    )
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user_optional(token: str = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False))):
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

class AuditRequest(BaseModel):
    session_id: str
    scenario: str

# Simple JSON-based database for local persistence
DB_FILE = "db.json"

def read_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def write_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.get("/api/health")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dhmc-python-backend"}

@app.post("/api/audit/trigger")
def trigger_audit(request: AuditRequest, current_user: dict = Depends(get_current_user_optional)):
    return {
        "status": "accepted",
        "message": f"Audit triggered for session {request.session_id}",
        "user": current_user.get("username") if current_user else "anonymous"
    }

@app.get("/api/sessions")
def get_sessions():
    db = read_db()
    # Return basic metadata sorted by date descending
    sessions = []
    for sid, data in db.items():
        sessions.append({
            "id": data.get("id"),
            "sessionId": data.get("sessionId"),
            "date": data.get("date"),
            "applicantName": data.get("applicantName"),
            "loanAmount": data.get("loanAmount"),
            "verdict": data.get("auditResults", {}).get("verdict", "UNKNOWN"),
            "scenarioId": data.get("scenarioId"),
            "scenarioTitle": data.get("scenarioTitle"),
        })
    
    sessions.sort(key=lambda x: x.get("date", ""), reverse=True)
    return sessions

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    db = read_db()
    if session_id not in db:
        raise HTTPException(status_code=404, detail="Session not found")
    return db[session_id]

@app.post("/api/sessions")
def save_session(data: dict, current_user: dict = Depends(get_current_user_optional)):
    db = read_db()
    session_id = data.get("id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session id")
    
    # Enrich data
    if "date" not in data:
        data["date"] = datetime.utcnow().isoformat()
        
    db[session_id] = data
    write_db(db)
    
    return {"success": True, "session": {"id": session_id}}

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, current_user: dict = Depends(get_current_user_optional)):
    db = read_db()
    if session_id not in db:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del db[session_id]
    write_db(db)
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
