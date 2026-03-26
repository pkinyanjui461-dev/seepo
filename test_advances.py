import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seepo_project.settings')
django.setup()

from finance.views import _get_perf_summary

class MockEntry:
    def __init__(self, section, is_paid=False, amount=Decimal('0'), tertiary_amount=Decimal('0'), secondary_amount=Decimal('0'), description=''):
        self.section = section
        self.is_paid = is_paid
        self.amount = amount
        self.tertiary_amount = tertiary_amount
        self.secondary_amount = secondary_amount
        self.description = description

def test_summary():
    sections = {
        'A': [
            MockEntry('A', is_paid=True, amount=Decimal('100')), 
            MockEntry('A', is_paid=False, amount=Decimal('200')), 
        ],
        'B': [
            MockEntry('B', amount=Decimal('0'), secondary_amount=Decimal('0'), tertiary_amount=Decimal('300')) 
        ],
        'E': []
    }
    totals = {'savings_share_cf': Decimal('0'), 'loan_balance_cf': Decimal('0')}
    summary = _get_perf_summary(None, totals, sections)
    print(f"Calculated Advance in Summary: {summary['adv']}")
    if summary['adv'] == Decimal('500'):
        print("Summary Calculation Passed!")
    else:
        print("Summary Calculation Failed!")

if __name__ == '__main__':
    test_summary()
