from fastapi import FastAPI

from modules.study.routes import router as study_router


app = FastAPI(title="JARVIS - module 6 (test)")

app.include_router(study_router)