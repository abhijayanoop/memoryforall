from fastapi import FastAPI

app = FastAPI(title="memoryforall")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
