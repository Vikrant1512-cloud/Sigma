from fastapi import FastAPI

from app.core.database import Base, engine
from app.models.user import User


Base.metadata.create_all(bind=engine)


app = FastAPI(title="Sigma API")


@app.get("/")
def root():
    return {
        "message": "Sigma API is running",
        "project": "Sigma"
    }