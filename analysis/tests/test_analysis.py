"""Test for split_dates_by_num_days and all_present in analysis script"""


from savings_analysis import split_dates_by_num_days
from datetime import datetime, timedelta
import pytest

START_DATE = datetime(2026, 9, 1)
END_DATE = datetime(2026, 10, 1)
NUM_DAYS = 13

# ---- helpers ----
def to_datetime(dates: list[tuple[str, str]]) -> list[tuple[datetime, datetime]]:
    return [(datetime.strptime(d[0], '%Y-%m-%dT%H:%M:%SZ'),
             datetime.strptime(d[1], '%Y-%m-%dT%H:%M:%SZ')) for d in dates]

# split_dates_by_num_days(start_date, end_date, num_days)
# all_present(values: list[int | None]) -> list[int] | None

def test_chunks_dont_overlap():
    dates = to_datetime(split_dates_by_num_days(START_DATE, END_DATE, NUM_DAYS))
    assert len(dates) == 3
    for i in range(len(dates)-1):
        assert dates[i][1] < dates[i+1][0]

def test_each_chunk_at_most_num_days_long():
    dates = to_datetime(split_dates_by_num_days(START_DATE, END_DATE, NUM_DAYS))
    for date in dates:
        assert date[1] - date[0] <= timedelta(days=NUM_DAYS)


def test_gaps_are_1_minute_long():
    dates = to_datetime(split_dates_by_num_days(START_DATE, END_DATE, NUM_DAYS))
    for date in dates:
        assert date[1] - date[0] <= timedelta(days=NUM_DAYS)

def test_chunks_cover_full_range():
    dates = to_datetime(split_dates_by_num_days(START_DATE, END_DATE, NUM_DAYS))
    assert dates[0][0].date() == START_DATE.date()
    assert dates[-1][1].date() == END_DATE.date()


@pytest.mark.parametrize("start_date, end_date, expected",[
    (datetime(2026, 9, 1), datetime(2026, 9, 1 + NUM_DAYS), 1),
    (datetime(2026, 9, 1), datetime(2026, 9, 1 + 2*NUM_DAYS), 2),
])
def test_multiples_of_num_days(start_date, end_date, expected):
    dates = split_dates_by_num_days(start_date, end_date, NUM_DAYS)
    assert len(dates) == expected

