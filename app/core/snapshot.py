import os
import shutil
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.models import SystemSnapshot

DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "local_erp.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

def create_snapshot(user_id: int = None, is_auto: bool = True):
    """
    현재 SQLite 데이터베이스 파일의 물리적 복사본을 생성하고
    SYSTEM_SNAPSHOT 테이블에 이력을 기록합니다.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "auto" if is_auto else f"manual_user_{user_id}"
    snapshot_filename = f"snapshot_{prefix}_{timestamp}.db"
    snapshot_path = os.path.join(BACKUP_DIR, snapshot_filename)
    
    # DB 파일 복사 (WAL 모드 주의: 가능하면 체크포인트 후 복사가 좋으나, SQLite 로컬 환경이므로 바로 복사)
    try:
        shutil.copy2(DB_PATH, snapshot_path)
    except FileNotFoundError:
        print(f"Error: Database file not found at {DB_PATH}")
        return None
    except Exception as e:
        print(f"Error creating snapshot: {e}")
        return None

    # 스냅샷 테이블에 기록
    db = SessionLocal()
    try:
        new_snapshot = SystemSnapshot(
            snapshot_path=snapshot_path,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            created_by=user_id,
            is_auto=is_auto
        )
        db.add(new_snapshot)
        db.commit()
        db.refresh(new_snapshot)
        return new_snapshot
    except Exception as e:
        db.rollback()
        print(f"Error recording snapshot to DB: {e}")
        return None
    finally:
        db.close()

def _auto_snapshot_job():
    print(f"[{datetime.now()}] Running scheduled auto snapshot...")
    create_snapshot(is_auto=True)

# 백그라운드 스케줄러 인스턴스
scheduler = BackgroundScheduler()
scheduler.add_job(_auto_snapshot_job, "interval", hours=3)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
