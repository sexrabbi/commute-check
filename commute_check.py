# -*- coding: utf-8 -*-
"""
工作日通勤监控 — GitHub Actions 版
每个工作日 7:40-8:00 (UTC+8) 每 5 分钟查询高德路线，
预估到达时间并通过 Server酱推送到微信。
仅用标准库，零依赖。
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# ============== 配置（优先读环境变量） ==============
AMAP_KEY = os.environ.get("AMAP_KEY", "")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")

HOME_ADDRESS = os.environ.get("HOME_ADDRESS", "太仓市湖境天著雅苑")
COMPANY_ADDRESS = os.environ.get("COMPANY_ADDRESS", "苏州市吴中区亭和路与临江路交叉口")
HOME_CITY = os.environ.get("HOME_CITY", "太仓")
COMPANY_CITY = os.environ.get("COMPANY_CITY", "苏州")

WORK_START_HOUR = int(os.environ.get("WORK_START_HOUR", "9"))
WORK_START_MINUTE = int(os.environ.get("WORK_START_MINUTE", "0"))
BUFFER_MINUTES = int(os.environ.get("BUFFER_MINUTES", "15"))

# 中国标准时间 UTC+8
CST = timezone(timedelta(hours=8))
# ==================================================


def http_get_json(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{qs}", headers={"User-Agent": "commute-check/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "commute-check/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(address: str, city: str) -> str:
    resp = http_get_json(
        "https://restapi.amap.com/v3/geocode/geo",
        {"address": address, "city": city, "key": AMAP_KEY, "output": "JSON"},
    )
    if resp.get("status") == "1" and resp.get("geocodes"):
        loc = resp["geocodes"][0]["location"]
        print(f"  geocode: {address} -> {loc}")
        return loc
    raise RuntimeError(f"Geocode failed: {address}  resp={resp}")


def get_driving_info(origin: str, destination: str) -> dict:
    resp = http_get_json(
        "https://restapi.amap.com/v3/direction/driving",
        {
            "origin": origin,
            "destination": destination,
            "key": AMAP_KEY,
            "strategy": 20,
            "extensions": "base",
            "output": "JSON",
        },
    )
    if resp.get("status") != "1":
        raise RuntimeError(f"Route failed: {resp}")

    paths = resp.get("route", {}).get("paths", [])
    if not paths:
        raise RuntimeError("No route found")

    best = min(paths, key=lambda p: int(p.get("duration", 99999)))
    duration = int(best.get("duration", 0))
    distance = int(best.get("distance", 0))
    return {
        "duration_min": round(duration / 60),
        "distance_km": round(distance / 1000, 1),
    }


def send_wechat(title: str, content: str) -> bool:
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    try:
        r = http_post_form(url, {"title": title, "desp": content})
        if r.get("code") == 0:
            print(f"  WeChat sent: {title}")
            return True
        print(f"  WeChat failed: {r}")
        return False
    except Exception as e:
        print(f"  WeChat error: {e}")
        return False


def main():
    if not AMAP_KEY or not SERVERCHAN_KEY:
        print("ERROR: AMAP_KEY / SERVERCHAN_KEY not set")
        sys.exit(1)

    now = datetime.now(CST)
    weekday = now.weekday()
    if weekday >= 5:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Weekend, skip.")
        return

    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Checking commute ...")

    home = geocode(HOME_ADDRESS, HOME_CITY)
    company = geocode(COMPANY_ADDRESS, COMPANY_CITY)
    info = get_driving_info(home, company)
    print(f"  Route: {info['distance_km']} km / {info['duration_min']} min")

    duration_min = info["duration_min"]
    dist_km = info["distance_km"]
    eta = now + timedelta(minutes=duration_min + BUFFER_MINUTES)
    work_start = now.replace(
        hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0
    )
    latest_leave = work_start - timedelta(minutes=duration_min + BUFFER_MINUTES)
    late_by_min = (eta - work_start).total_seconds() / 60
    eta_str = eta.strftime("%H:%M")
    leave_str = latest_leave.strftime("%H:%M")

    if eta > work_start:
        title = f"⚠️ 迟到风险！预计 {eta_str} 到"
        body = (
            f"**预计到达：{eta_str}**（晚约 {int(late_by_min)} 分钟）\n\n"
            f"- 里程 {dist_km} km，行车约 {duration_min} 分钟\n"
            f"- 上班 {WORK_START_HOUR:02d}:{WORK_START_MINUTE:02d}\n"
            f"- 建议 **{leave_str}** 前出发\n"
            f"- 含缓冲 {BUFFER_MINUTES} 分钟\n\n"
            f"> 查询于 {now.strftime('%H:%M:%S')} (CST)"
        )
    else:
        margin_min = int(-late_by_min)
        if margin_min >= 30:
            status = "🟢 路况畅通"
        elif margin_min >= 15:
            status = "🟡 路况正常"
        else:
            status = "🟠 时间刚好"
        title = f"{status} 预计 {eta_str} 到"
        body = (
            f"**预计到达：{eta_str}**（富余 {margin_min} 分钟）\n\n"
            f"- 里程 {dist_km} km，行车约 {duration_min} 分钟\n"
            f"- 上班 {WORK_START_HOUR:02d}:{WORK_START_MINUTE:02d}\n"
            f"- 最晚 **{leave_str}** 出发\n\n"
            f"> 查询于 {now.strftime('%H:%M:%S')} (CST)"
        )

    send_wechat(title, body)
    print("Done.")


if __name__ == "__main__":
    main()
