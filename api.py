import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="DHMC Python Backend API", version="1.0.0")

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_dhmc_key_change_in_prod")
if not os.getenv("JWT_SECRET"):
    logger.warning(
        "JWT_SECRET is not set — using insecure default. "
        "Set JWT_SECRET in your environment for production."
    )
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

class AuditRequest(BaseModel):
    session_id: str
    scenario: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dhmc-python-backend"}

@app.post("/api/audit/trigger")
def trigger_audit(request: AuditRequest, current_user: dict = Depends(get_current_user)):
    """
    Triggers an asynchronous DHMC LangGraph audit session.
    In a full production environment, this would push a task to Celery/Redis
    rather than running synchronously in the web thread.
    """
    # Example placeholder for Celery task dispatch:
    # dhmc_audit_task.delay(request.session_id, request.scenario)
    
    return {
        "status": "accepted",
        "message": f"Audit triggered for session {request.session_id}",
        "user": current_user.get("username")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
