# ==================== 3. backend.py ====================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routes import router

app = FastAPI(
    title="Build Club Smart Attendance API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)