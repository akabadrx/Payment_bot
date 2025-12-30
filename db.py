import sqlite3
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DB_FILE = "bot_state.db"

import datetime

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state_data TEXT,
                last_updated TIMESTAMP,
                reminder_sent INTEGER DEFAULT 0
            )
        """)
        
        # Migrations: Add columns if they don't exist (for existing DBs)
        try:
            cursor.execute("ALTER TABLE user_states ADD COLUMN last_updated TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE user_states ADD COLUMN reminder_sent INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def get_user_state(user_id: int) -> Dict:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Create column if not exists happens in init, but select * includes new columns
        cursor.execute("SELECT state_data FROM user_states WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return {}
    except Exception as e:
        logger.error(f"Failed to get user state for {user_id}: {e}")
        return {}

def update_user_state(user_id: int, state_data: Dict):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        json_data = json.dumps(state_data)
        now = datetime.datetime.now()
        
        # We use INSERT OR REPLACE. We must provide values for all columns we care about,
        # otherwise they might get reset to default or NULL.
        # last_updated -> NOW
        # reminder_sent -> 0 (User active, so reset reminder flag)
        cursor.execute("""
            INSERT OR REPLACE INTO user_states (user_id, state_data, last_updated, reminder_sent)
            VALUES (?, ?, ?, 0)
        """, (user_id, json_data, now))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update user state for {user_id}: {e}")

def delete_user_state(user_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to delete user state for {user_id}: {e}")

def get_abandoned_users(hours_threshold=2) -> list[tuple[int, Dict]]:
    """Returns list of (user_id, state_data) for users inactive > threshold hours."""
    abandoned = []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        limit_time = datetime.datetime.now() - datetime.timedelta(hours=hours_threshold)
        
        # Select users who haven't been reminded yet
        cursor.execute("""
            SELECT user_id, state_data FROM user_states 
            WHERE reminder_sent = 0 
            AND last_updated < ?
        """, (limit_time,))
        
        rows = cursor.fetchall()
        for uid, json_str in rows:
            try:
                data = json.loads(json_str)
                # Filter out those who are already completed or minimal state
                if data.get("stage") == "completed" or not data.get("stage"):
                    continue
                abandoned.append((uid, data))
            except:
                pass
        
        conn.close()
    except Exception as e:
        logger.error(f"Failed to get abandoned users: {e}")
    return abandoned

def mark_reminder_sent(user_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_states SET reminder_sent = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to mark reminder sent for {user_id}: {e}")

def get_incomplete_users() -> list[int]:
    """Returns list of user_ids who have NOT completed the registration."""
    user_ids = []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, state_data FROM user_states")
        rows = cursor.fetchall()
        
        for uid, json_str in rows:
            try:
                data = json.loads(json_str)
                if data.get("stage") != "completed":
                    user_ids.append(uid)
            except:
                pass
        
        conn.close()
    except Exception as e:
        logger.error(f"Failed to get incomplete users: {e}")
    return user_ids

def get_stats_counts() -> Dict[str, int]:
    """Returns total users and counts per course."""
    stats = {"total": 0, "courses": {}}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM user_states")
        stats["total"] = cursor.fetchone()[0]
        
        # Group by course
        # logic: iterate all, parse json. SQL cant parse json easily in default sqlite build without extensions
        # simple approach: load all and count in python (safe for small-medium scale)
        cursor.execute("SELECT state_data FROM user_states")
        rows = cursor.fetchall()
        
        course_counts = {}
        for (json_str,) in rows:
            try:
                data = json.loads(json_str)
                c_key = data.get("course", "unknown")
                course_counts[c_key] = course_counts.get(c_key, 0) + 1
            except:
                pass
        
        stats["courses"] = course_counts
        conn.close()
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
    
    return stats

def get_funnel_stats() -> Dict[str, int]:
    """Returns counts of users at each stage."""
    stage_counts = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT state_data FROM user_states")
        rows = cursor.fetchall()
        
        for (json_str,) in rows:
            try:
                data = json.loads(json_str)
                s_key = data.get("stage", "unknown")
                stage_counts[s_key] = stage_counts.get(s_key, 0) + 1
            except:
                pass
                
        conn.close()
    except Exception as e:
        logger.error(f"Failed to get funnel stats: {e}")
    
    return stage_counts

# --- COUPONS ---
def add_coupon(code: str, discount_percent: int, usage_limit: int = 0, course_key: str = None):
    """usage_limit=0 means infinite. course_key=None means valid for all courses."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                usage_count INTEGER DEFAULT 0,
                usage_limit INTEGER DEFAULT 0,
                course_key TEXT DEFAULT NULL
            )
        """)
        
        # Migration: Add columns if missing
        try: cursor.execute("ALTER TABLE coupons ADD COLUMN usage_count INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE coupons ADD COLUMN usage_limit INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE coupons ADD COLUMN course_key TEXT DEFAULT NULL")
        except: pass

        cursor.execute("""
            INSERT OR REPLACE INTO coupons (code, discount_percent, usage_count, usage_limit, course_key) 
            VALUES (?, ?, 0, ?, ?)
        """, (code.upper().strip(), discount_percent, usage_limit, course_key))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to add coupon: {e}")

def get_coupon(code: str, user_course: str = None) -> Optional[int]:
    """Returns discount percent if valid, under limit, and matches course (if specified).
    Returns None if invalid, expired, or wrong course."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT discount_percent, usage_count, usage_limit, course_key FROM coupons WHERE code = ?", (code.upper().strip(),))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            percent, count, limit, coupon_course = row
            # If limit is 0, it's infinite. If limit > 0, count must be < limit.
            if limit > 0 and count >= limit:
                return None
            # If coupon is course-specific, check if user's course matches
            if coupon_course and user_course and coupon_course != user_course:
                return None
            return percent
        return None
    except Exception as e:
        logger.error(f"Failed to get coupon: {e}")
        return None

def redeem_coupon(code: str):
    """Increments usage count for a coupon."""
    if not code: return
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE coupons SET usage_count = usage_count + 1 WHERE code = ?", (code.upper().strip(),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to redeem coupon: {e}")

def delete_coupon(code: str):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM coupons WHERE code = ?", (code.upper().strip(),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to delete coupon: {e}")

def list_coupons() -> Dict[str, Dict]:
    result = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Ensure schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                usage_count INTEGER DEFAULT 0,
                usage_limit INTEGER DEFAULT 0
            )
        """)
        
        # Migration attempt just in case list is called first
        try: cursor.execute("ALTER TABLE coupons ADD COLUMN usage_count INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE coupons ADD COLUMN usage_limit INTEGER DEFAULT 0")
        except: pass

        cursor.execute("SELECT code, discount_percent, usage_count, usage_limit FROM coupons")
        rows = cursor.fetchall()
        for c, p, count, limit in rows:
            result[c] = {"percent": p, "count": count, "limit": limit}
        conn.close()
    except Exception as e:
        logger.error(f"Failed to list coupons: {e}")
    return result
