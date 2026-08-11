"""
나만의 CGV 예매 오픈 알리미
------------------------------------
- 감시 대상: siteNo(지점) + scnsNo(상영관) + movNo(영화) 하나
- CGV 신 API(searchSchByMov)를 일정 간격으로 조회해서
  '이전에는 없던 상영 일정'이 새로 생기면 디스코드로 알림을 보낸다.
- 이전 결과는 로컬 json 파일(state.json)에 저장해서, 재시작해도 중복 알림이 안 가도록 한다.

사용법:
  1. 아래 CONFIG 섹션의 값들을 본인 것으로 채운다.
  2. .env 파일에 DISCORD_BOT_TOKEN=본인봇토큰 한 줄 넣어둔다.
  3. pip install requests python-dotenv --break-system-packages (윈도우는 --break-system-packages 없이)
  4. python my_cgv_notifier.py 로 실행 (계속 실행되는 상태로 둬야 함)
"""

import os
import json
import time
import random
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIG (본인 값으로 수정) ====================

SITE_NO = "0199"          # CGV 천호
SCNS_NO = "001"           # 1관 (IMAX)
MOV_NO = "30001323"       # 오디세이
CO_CD = "A420"            # CGV 고정 코드 (보통 안 바꿔도 됨)
RTCTL_SCOP_CD = "08"      # 캡처했던 요청 그대로 사용

# 앞으로 며칠치 날짜를 확인할지 (예매는 보통 몇 주 전에 열리므로 넉넉하게)
DAYS_AHEAD = 21

# 알림 보낼 디스코드 채널 ID (본인 서버의 채널 ID로 교체)
DISCORD_CHANNEL_ID = "1536746886151544842"

# 폴링 간격 (10분 기준, 초 단위) + 약간의 랜덤(지터) 추가
POLL_INTERVAL_SECONDS = 10 * 60
JITTER_SECONDS = 30

# 상태 저장 파일 (같은 폴더에 생김)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# ====================================================================

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://cgv.co.kr/",
    "Origin": "https://cgv.co.kr",
}

API_URL = "https://cgv.co.kr/api/v1/booking/searchSchByMov"


def load_state():
    """이전에 감지했던 '이미 열려있던 날짜' 목록을 불러온다."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(known_dates):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(known_dates)), f, ensure_ascii=False, indent=2)


def send_discord_message(content: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={"content": content}, timeout=10)
    if resp.status_code not in (200, 201):
        print(f"[디스코드 전송 실패] status={resp.status_code} body={resp.text}")


def check_date(scn_ymd: str) -> bool:
    """해당 날짜에 지정한 상영관(scnsNo)에 상영 일정이 있으면 True."""
    params = {
        "coCd": CO_CD,
        "siteNo": SITE_NO,
        "scnYmd": scn_ymd,
        "movNo": MOV_NO,
        "rtctlScopCd": RTCTL_SCOP_CD,
    }
    try:
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)
    except requests.RequestException as e:
        print(f"[요청 실패] {scn_ymd}: {e}")
        return False

    if resp.status_code == 429:
        print("[경고] 429 Too Many Requests - 잠시 쉬었다가 재시도합니다.")
        time.sleep(60)
        return False

    if resp.status_code != 200:
        print(f"[비정상 응답] {scn_ymd}: status={resp.status_code}")
        return False

    data = resp.json().get("data") or []
    return any(item.get("scnsNo") == SCNS_NO for item in data)


def run_once(known_dates: set) -> set:
    today = datetime.date.today()
    newly_found = []

    for i in range(DAYS_AHEAD):
        scn_ymd = (today + datetime.timedelta(days=i)).strftime("%Y%m%d")
        has_schedule = check_date(scn_ymd)

        if has_schedule and scn_ymd not in known_dates:
            newly_found.append(scn_ymd)
            known_dates.add(scn_ymd)

        # CGV 서버에 너무 몰아치지 않도록 요청 사이 살짝 텀
        time.sleep(1)

    if newly_found:
        dates_str = ", ".join(newly_found)
        message = (
            f"🎬 **예매 오픈 감지!**\n"
            f"CGV 천호 IMAX (1관) - 오디세이\n"
            f"새로 열린 날짜: {dates_str}\n"
            f"https://cgv.co.kr/cnm/movieBook/movie"
        )
        print(message)
        send_discord_message(message)

    return known_dates


def main():
    print("CGV 개인 알리미 시작 (10분 간격, 종료하려면 Ctrl+C)")
    known_dates = load_state()

    while True:
        try:
            known_dates = run_once(known_dates)
            save_state(known_dates)
        except Exception as e:
            print(f"[예외 발생] {e}")

        sleep_time = POLL_INTERVAL_SECONDS + random.randint(-JITTER_SECONDS, JITTER_SECONDS)
        print(f"다음 확인까지 {sleep_time}초 대기...")
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
