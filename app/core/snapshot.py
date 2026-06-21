import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal, BASE_DIR, DB_PATH, BACKUP_DIR
from app.models import SystemSnapshot


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

    # WAL 체크포인트 후 복사 (데이터 무결성 보장)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception as e:
        print(f"Warning: WAL checkpoint failed: {e}")

    # DB 파일 복사
    try:
        shutil.copy2(DB_PATH, snapshot_path)
    except FileNotFoundError:
        print(f"Error: Database file not found at {DB_PATH}")
        return None
    except Exception as e:
        print(f"Error creating snapshot: {e}")
        return None

    # 오래된 백업 정리 (30일 초과 또는 240개 초과 시 삭제)
    _rotate_backups()

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


def _rotate_backups(max_age_days: int = 30, max_files: int = 240):
    """오래된 스냅샷 백업 파일 정리"""
    try:
        backup_files = sorted(
            [
                os.path.join(BACKUP_DIR, f)
                for f in os.listdir(BACKUP_DIR)
                if f.startswith("snapshot_") and f.endswith(".db")
            ],
            key=os.path.getmtime,
        )
    except FileNotFoundError:
        return

    # 30일 초과 파일 삭제
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for filepath in backup_files:
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
        except Exception:
            pass

    # 최대 개수 초과 시 오래된 것부터 삭제
    try:
        remaining = sorted(
            [
                os.path.join(BACKUP_DIR, f)
                for f in os.listdir(BACKUP_DIR)
                if f.startswith("snapshot_") and f.endswith(".db")
            ],
            key=os.path.getmtime,
        )
        while len(remaining) > max_files:
            os.remove(remaining.pop(0))
    except Exception:
        pass


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
        scheduler.shutdown(wait=False)
