# ce_utils.py
import datetime
from datetime import timezone, timedelta

def get_jst_now():
    return datetime.datetime.now(timezone(timedelta(hours=9))).strftime('%H:%M:%S')

def ce_log(role, step_message, target):
    now = get_jst_now()
    # 役割(RECEIVER/WORKER)を動的に変えられるようにします
    print(f"[{now}] [{role}] {step_message}：{target}", flush=True)
