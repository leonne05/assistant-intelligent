from fastapi import FastAPI

from modules.study.routes import router as study_router
from modules.meetings.routes import router as meetings_router
from modules.meetings.planning_routes import router as meetings_preparation_router
from modules.meetings.planning_routes import agenda_router
from modules.meetings.follow_up_routes import router as follow_up_router


app = FastAPI(title="JARVIS - module 6 (test)")

app.include_router(study_router)
app.include_router(meetings_router)
app.include_router(meetings_preparation_router)
app.include_router(agenda_router)
app.include_router(follow_up_router)