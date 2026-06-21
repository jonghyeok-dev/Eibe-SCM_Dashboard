from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
import os
import io
import math
import urllib.parse
from datetime import datetime, date, timedelta
import pandas as pd

from app.database import get_db, BASE_DIR, BACKUP_DIR
from app.models import *
from app.schemas import *
from app.core.auth import verify_password, get_password_hash, create_access_token, get_current_user, get_current_admin
from app.core.snapshot import create_snapshot

try:
    from app.core.excel_parser import generate_template, get_template_filename, parse_inventory_excel, generate_order_plan_export, TEMPLATE_LABELS
except Exception:
    TEMPLATE_LABELS = {}

try:
    from app.core.forecasting import *
except Exception:
    pass

router = APIRouter(include_in_schema=False)
WEB_DIR = os.path.join(BASE_DIR, "web")
templates = Jinja2Templates(directory=os.path.join(WEB_DIR, "templates"))

@router.get("/", include_in_schema=False)
async def serve_dashboard(request: Request):
    """메인 통합 대시보드 화면"""
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "dashboard"})


@router.get("/inventory", include_in_schema=False)
async def serve_inventory(request: Request):
    return templates.TemplateResponse("inventory.html", {"request": request, "active_page": "inventory"})


@router.get("/inventory/transfer", include_in_schema=False)
async def serve_inventory_transfer(request: Request):
    """이관 계획 페이지 — inventory.html의 이관 탭으로 라우팅"""
    return templates.TemplateResponse("inventory.html", {"request": request, "active_page": "inventory", "tab": "transfer"})


@router.get("/expiry", include_in_schema=False)
async def serve_expiry(request: Request):
    return templates.TemplateResponse("expiry.html", {"request": request, "active_page": "expiry"})


@router.get("/order-plan", include_in_schema=False)
async def serve_order_plan(request: Request):
    """월 1회 발주 제안 편집 및 수정 저장 화면"""
    return templates.TemplateResponse("order_plan.html", {"request": request, "active_page": "order_plan"})


@router.get("/matching", include_in_schema=False)
async def serve_matching(request: Request):
    return templates.TemplateResponse("matching.html", {"request": request, "active_page": "matching"})


@router.get("/users", include_in_schema=False)
async def serve_users(request: Request):
    return templates.TemplateResponse("users.html", {"request": request, "active_page": "users"})


@router.get("/login", include_in_schema=False)
async def serve_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


