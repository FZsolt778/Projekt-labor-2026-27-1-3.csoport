from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from server.src.database import get_db
from server.API.auth.routes import router as auth_router
from server.API.user.routes import router as user_router
from server.API.parcel.routes import router as parcel_router
from server.API.courier.routes import router as courier_router
from server.API.warehouse.routes import router as warehouse_router
from server.API.stat.routes import router as stat_router

app = FastAPI(title="ProjektLab API")

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(parcel_router)
app.include_router(courier_router)
app.include_router(warehouse_router)
app.include_router(stat_router)

# Checks that the API is running and can reach the database
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
