from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
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

router = APIRouter()
WEB_DIR = os.path.join(BASE_DIR, "web")

@router.get("/api/users", response_model=List[UserAccountResponse], tags=["사용자 관리"])
def get_users(db: Session = Depends(get_db)):
    """전체 사용자 목록 조회"""
    return db.query(UserAccount).all()


@router.post("/api/users", response_model=UserAccountResponse, tags=["사용자 관리"])
def create_user(
    user: UserAccountCreate,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 계정 생성 (ADMIN 전용)"""
    existing = db.query(UserAccount).filter(UserAccount.username == user.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"사용자 '{user.username}' 이미 존재")
    db_user = UserAccount(
        username=user.username,
        password_hash=get_password_hash(user.password),
        role=user.role,
        name=user.name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.put("/api/users/{user_id}", response_model=MessageResponse, tags=["사용자 관리"])
def update_user(
    user_id: int,
    data: dict,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 정보 수정 (비밀번호/역할/이름)"""
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if "password" in data and data["password"]:
        user.password_hash = get_password_hash(data["password"])
    if "name" in data:
        user.name = data["name"]
    if "role" in data and data["role"] in ("ADMIN", "OPERATOR"):
        user.role = data["role"]
    db.commit()
    return MessageResponse(message="사용자 정보가 수정되었습니다")


@router.delete("/api/users/{user_id}", response_model=MessageResponse, tags=["사용자 관리"])
def delete_user(
    user_id: int,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 계정 삭제 (ADMIN 전용)"""
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user.username == "admin":
        raise HTTPException(status_code=403, detail="기본 관리자 계정은 삭제할 수 없습니다")
    db.delete(user)
    db.commit()
    return MessageResponse(message="삭제 완료", detail=f"사용자 '{user.username}' 삭제됨")


