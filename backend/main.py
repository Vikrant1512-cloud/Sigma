from fastapi import FastAPI

app = FastAPI(title="Sigma API")


@app.get("/")
def root():
    return {
        "message": "Sigma API is running",
        "project": "Sigma"
    }