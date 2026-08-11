"""
GitHub Actions용 단발성 실행 스크립트.
my_cgv_notifier.py 안의 함수들을 그대로 재사용해서,
'한 번만 확인하고 끝내는' 버전이다.
(반복 실행은 GitHub Actions의 cron 스케줄이 담당한다.)
"""

from my_cgv_notifier import load_state, save_state, run_once

if __name__ == "__main__":
    known_dates = load_state()
    known_dates = run_once(known_dates)
    save_state(known_dates)
