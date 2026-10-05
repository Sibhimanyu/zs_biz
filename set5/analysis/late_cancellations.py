"""Which cancellations hurt most, and who makes them?

Source: Booking Vs Cancellations CSV (20,337 cancellation / no-show records).
The file has dates, not hours, so "the last 24 hours" is approximated as
arrival date minus reservation_status_date <= 1 day. No-shows are recorded on
the arrival date (0 days).

Run:  python3 analysis/late_cancellations.py
Writes analysis/results.json (read by the deck builder).
"""
import csv, collections, datetime as dt, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "Booking Vs Cancellations_Booking Vs Cancellations.csv")
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']

rows = list(csv.DictReader(open(CSV)))
for r in rows:
    arr = dt.date(int(r['arrival_date_year']), MONTHS.index(r['arrival_date_month']) + 1,
                  int(r['arrival_date_day_of_month']))
    r['days_before'] = (arr - dt.date.fromisoformat(r['reservation_status_date'])).days
    r['nights'] = int(r['stays_in_week_nights']) + int(r['stays_in_weekend_nights'])
    r['value'] = float(r['adr']) * r['nights']          # estimated room value, dataset units
    r['lead'] = int(r['lead_time'])
    r['adults_n'] = int(r['adults'])
    r['no_show'] = r['reservation_status'] == 'No-Show'

N = len(rows)
late = [r for r in rows if 0 <= r['days_before'] <= 1]      # last ~24 hours
total_value = sum(r['value'] for r in rows)


def pct(a, b):
    return round(100 * a / b, 1)


def bucket(d):
    if d == 0: return 'Day of arrival'
    if d == 1: return '1 day'
    if d <= 3: return '2-3 days'
    if d <= 7: return '4-7 days'
    if d <= 30: return '8-30 days'
    if d <= 90: return '31-90 days'
    return '91+ days'


order = ['91+ days', '31-90 days', '8-30 days', '4-7 days', '2-3 days', '1 day', 'Day of arrival']
timing = collections.Counter(bucket(r['days_before']) for r in rows)

segments = ['Online TA', 'Offline TA/TO', 'Groups', 'Direct', 'Corporate']
seg_all = collections.Counter(r['market_segment'] for r in rows)
seg_late = collections.Counter(r['market_segment'] for r in late)


def late_rate(pred):
    base = [r for r in rows if pred(r)]
    hit = [r for r in late if pred(r)]
    return {'records': len(base), 'late': len(hit), 'late_rate': pct(len(hit), len(base)),
            'share_of_late': pct(len(hit), len(late))}


short = [r for r in late if r['lead'] <= 7]
solo_short = [r for r in short if r['adults_n'] == 1]

res = {
    'total_records': N,
    'late_records': len(late),
    'late_share': pct(len(late), N),
    'late_value_share': pct(sum(r['value'] for r in late), total_value),
    'late_no_show': sum(r['no_show'] for r in late),
    'late_active_cancel': sum(not r['no_show'] for r in late),
    'late_no_deposit_share': pct(sum(r['deposit_type'] == 'No Deposit' for r in late), len(late)),
    'timing': [{'bucket': b, 'records': timing[b], 'share': pct(timing[b], N)} for b in order],
    'funnel': [
        {'label': 'All cancellation records', 'n': N},
        {'label': 'In the last 24 hours', 'n': len(late)},
        {'label': '...booked within 7 days of arrival', 'n': len(short)},
        {'label': '...a solo traveller', 'n': len(solo_short)},
    ],
    'segments': [{'segment': s, 'share_all': pct(seg_all[s], N), 'share_late': pct(seg_late[s], len(late)),
                  'late_rate': pct(seg_late[s], seg_all[s])} for s in segments],
    'groups': {
        'Booked 91+ days ahead': late_rate(lambda r: r['lead'] >= 91),
        'Groups segment': late_rate(lambda r: r['market_segment'] == 'Groups'),
        'Two adults': late_rate(lambda r: r['adults_n'] == 2),
        'Arrives in February': late_rate(lambda r: r['arrival_date_month'] == 'February'),
        'One-night stay': late_rate(lambda r: r['nights'] == 1),
        'Solo traveller': late_rate(lambda r: r['adults_n'] == 1),
        'Booked within 7 days': late_rate(lambda r: r['lead'] <= 7),
        'Solo, booked within 7 days': late_rate(lambda r: r['adults_n'] == 1 and r['lead'] <= 7),
        'Direct/Corporate, within 7 days': late_rate(
            lambda r: r['market_segment'] in ('Direct', 'Corporate') and r['lead'] <= 7),
    },
    'short_notice_profile': {
        'records': len(short),
        'one_night_share': pct(sum(r['nights'] == 1 for r in short), len(short)),
        'solo_share': pct(sum(r['adults_n'] == 1 for r in short), len(short)),
        'two_adults_share': pct(sum(r['adults_n'] == 2 for r in short), len(short)),
        'no_requests_share': pct(sum(int(r['total_of_special_requests']) == 0 for r in short), len(short)),
        'no_show_share': pct(sum(r['no_show'] for r in short), len(short)),
    },
    'baseline_pct_91plus': pct(sum(1 for r in rows if r['lead'] >= 91), N),
}
json.dump(res, open(os.path.join(HERE, 'results.json'), 'w'), indent=2)
print(json.dumps(res, indent=2))
