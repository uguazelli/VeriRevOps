from fastapi import FastAPI, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import base64
import json
from typing import Optional

from app.database import engine, Base, get_db, SessionLocal
from app.models import User

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Legacy Auth App")

def get_sso_userinfo(request: Request) -> Optional[dict]:
    userinfo_b64 = request.headers.get("x-userinfo") or request.headers.get("X-Userinfo")
    if not userinfo_b64:
        return None
    try:
        padded = userinfo_b64 + "=" * ((4 - len(userinfo_b64) % 4) % 4)
        userinfo_json = base64.b64decode(padded).decode('utf-8')
        return json.loads(userinfo_json)
    except Exception as e:
        print(f"DEBUG SSO - Error parsing X-Userinfo: {e}")
    return None

@app.middleware("http")
async def sso_identity_injector(request: Request, call_next):
    # This middleware intercepts requests and seamlessly upgrades the legacy 
    # session with the SSO identity before the endpoints even see it!
    userinfo = get_sso_userinfo(request)
    
    if userinfo:
        # 1. We extract the primary email or username from the SSO payload
        sso_email = userinfo.get("preferred_username") or userinfo.get("email")
        
        if sso_email:
            # 2. We look up this user in our legacy database
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == sso_email).first()
                
                # 3. Just-In-Time (JIT) Provisioning
                # If they don't exist in the legacy DB yet, but APISIX verified them, 
                # we seamlessly auto-create their legacy profile!
                if not user:
                    user = User(username=sso_email, password_hash="sso_managed_identity")
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                # 4. Inject the local legacy ID into the session perfectly!
                request.scope["session"]["user_id"] = user.id
            finally:
                db.close()
            
    return await call_next(request)

# Add standard session middleware (must be added after the custom middleware so it wraps it)
app.add_middleware(
    SessionMiddleware, 
    secret_key="your-super-secret-key-for-lab",
    session_cookie="legacy_lab_session"
)

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.post("/register", response_class=HTMLResponse)
async def post_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html", 
            context={"error": "Username already exists."}
        )
    
    new_user = User(
        username=username, 
        password_hash=User.get_password_hash(password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Auto-login upon registration
    request.session["user_id"] = new_user.id
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login", response_class=HTMLResponse)
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.verify_password(password):
        return templates.TemplateResponse(
            request=request,
            name="login.html", 
            context={"error": "Invalid username or password"}
        )
    
    request.session["user_id"] = user.id
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    return templates.TemplateResponse(
        request=request,
        name="profile.html", 
        context={"username": user.username}
    )

@app.api_route("/logout", methods=["GET", "POST"])
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
