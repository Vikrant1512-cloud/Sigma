from fastapi import FastAPI

app = FastAPI(
    title="Sigma API",
    description="Backend API for the Sigma mathematics paper library",
    version="1.0.0",
)

@app.get("/")
def root():
    return {
        "message": "Sigma API is running",
        "project": "Sigma",
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
