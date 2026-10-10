from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from server.src.database import get_db

app = FastAPI(title="ProjektLab API")

# Checks that the API is running and can reach the database
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
