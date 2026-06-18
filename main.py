from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from database import engine, Base
from routers import doctors, slots, appointments, admin, nhi_queue

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fleur 小兒科診所 掛號系統")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Register API routers
app.include_router(doctors.router)
app.include_router(slots.router)
app.include_router(appointments.router)
app.include_router(admin.router)
app.include_router(nhi_queue.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/booking", response_class=HTMLResponse)
def booking(request: Request):
    return templates.TemplateResponse("booking.html", {"request": request})


@app.get("/confirmation", response_class=HTMLResponse)
def confirmation(request: Request):
    return templates.TemplateResponse("confirmation.html", {"request": request})


@app.get("/lookup", response_class=HTMLResponse)
def lookup(request: Request):
    return templates.TemplateResponse("lookup.html", {"request": request})


@app.get("/nhi-queue", response_class=HTMLResponse)
def nhi_queue_page(request: Request):
    return templates.TemplateResponse("nhi_queue.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})
