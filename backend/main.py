from fastapi import FastAPI
from fastapi import Depends

from app.api.auth import router as auth_router
from app.core.database import Base, engine
from app.models.user import User
from app.core.dependencies import get_current_user
from app.core.admin_dependencies import get_current_admin
from app.api.admin import router as admin_router


Base.metadata.create_all(bind=engine)


app = FastAPI(title="Sigma API")


app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "message": "Sigma API is running",
        "project": "Sigma"
    }

@app.get("/protected")
def protected_route(current_user = Depends(get_current_user)):
    return {
        "message": "You are authenticated!",
        "username": current_user.username,
    }

@app.get("/admin-test")
def admin_test(current_admin = Depends(get_current_admin)):
    return {
        "message": "Admin access confirmed!",
        "username": current_admin.username,
        "is_admin": current_admin.is_admin,
    }