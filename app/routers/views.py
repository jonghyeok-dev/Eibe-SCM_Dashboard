from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
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
@router.get("/", include_in_schema=False)
async def serve_dashboard():
    """메인 통합 대시보드 화면"""
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@router.get("/inventory", include_in_schema=False)
async def serve_inventory():
    return FileResponse(os.path.join(WEB_DIR, "inventory.html"))


@router.get("/inventory/transfer", include_in_schema=False)
async def serve_inventory_transfer():
    """이관 계획 페이지 — inventory.html의 이관 탭으로 라우팅"""
    return FileResponse(os.path.join(WEB_DIR, "inventory.html"))


@router.get("/expiry", include_in_schema=False)
async def serve_expiry():
    return FileResponse(os.path.join(WEB_DIR, "expiry.html"))


@router.get("/order-plan", include_in_schema=False)
async def serve_order_plan():
    """월 1회 발주 제안 편집 및 수정 저장 화면"""
    return FileResponse(os.path.join(WEB_DIR, "order_plan.html"))


@router.get("/matching", include_in_schema=False)
async def serve_matching():
    return FileResponse(os.path.join(WEB_DIR, "matching.html"))


@router.get("/users", include_in_schema=False)
async def serve_users():
    return FileResponse(os.path.join(WEB_DIR, "users.html"))


@router.get("/login", include_in_schema=False)
async def serve_login():
    return FileResponse(os.path.join(WEB_DIR, "login.html"))


