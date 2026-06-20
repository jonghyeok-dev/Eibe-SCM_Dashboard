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

@router.get("/api/health", response_model=MessageResponse, tags=["시스템"])
def health_check():
    """서버 상태 확인"""
    return MessageResponse(message="OK", detail="SCM ERP 서버가 정상 가동 중입니다.")


@router.post("/api/snapshot/manual", response_model=SystemSnapshotResponse, tags=["시스템 관리"])
def trigger_manual_snapshot(current_user: UserAccount = Depends(get_current_admin)):
    snapshot = create_snapshot(user_id=current_user.id, is_auto=False)
    if not snapshot:
        raise HTTPException(status_code=500, detail="스냅샷 생성 실패")
    return snapshot


@router.get("/api/snapshot/list", response_model=List[SystemSnapshotResponse], tags=["시스템 관리"])
def list_snapshots(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_admin),
):
    return db.query(SystemSnapshot).order_by(SystemSnapshot.created_at.desc()).limit(20).all()

import shutil
from app.database import DB_PATH

@router.post("/api/snapshot/restore/{snap_id}", response_model=MessageResponse, tags=["시스템 관리"])
def restore_snapshot(
    snap_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_admin),
):
    snapshot = db.query(SystemSnapshot).filter(SystemSnapshot.id == snap_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="스냅샷을 찾을 수 없습니다.")
    
    if not os.path.exists(snapshot.file_path):
        raise HTTPException(status_code=404, detail="스냅샷 파일이 물리적으로 존재하지 않습니다.")
    
    try:
        from app.database import engine
        engine.dispose()
        shutil.copy2(snapshot.file_path, DB_PATH)
        wal_path = DB_PATH + "-wal"
        shm_path = DB_PATH + "-shm"
        if os.path.exists(wal_path):
            os.remove(wal_path)
        if os.path.exists(shm_path):
            os.remove(shm_path)
        return MessageResponse(message="스냅샷 복원이 완료되었습니다. 브라우저를 새로고침합니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"복원 중 오류 발생: {str(e)}")
