#!/usr/bin/env python
"""
Parse PostgreSQL SQL backup and import relevant data into Django/sqlite.
Extracts groups, members, and monthly_forms from the backup.
"""
import os
import django
import re
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seepo_project.settings')
django.setup()

from groups.models import Group
from members.models import Member
from finance.models import MonthlyForm
from django.utils import timezone
from datetime import datetime, date
import uuid

SQL_FILE = '/e/Backup/pgwiz/seepo-main/db_backups/seepocok_main_public_before-feature-x_20260415_081634.sql/seepocok_main_public_before-feature-x_20260415_081634.sql'

def parse_sql_value(val_str):
    """Parse PostgreSQL value (handles NULL, strings with escapes, numbers)."""
    if val_str.upper() == 'NULL':
        return None
    if val_str.startswith("'") and val_str.endswith("'"):
        # PostgreSQL string value
        val = val_str[1:-1]
        # Unescape PostgreSQL escapes
        val = val.replace("''", "'")
        val = val.replace("\\'", "'")
        return val
    try:
        return int(val_str)
    except ValueError:
        try:
            return float(val_str)
        except ValueError:
            return val_str

def extract_insert_values(sql_line):
    """Extract the VALUES clause from a PostgreSQL INSERT statement."""
    # Match: INSERT INTO table (cols) VALUES (val1, val2, ...);
    match = re.search(r'VALUES\s*\((.*?)\);?\s*$', sql_line, re.IGNORECASE)
    if not match:
        return None
    values_str = match.group(1)
    # Parse CSV-like values handling quoted strings
    values = []
    current = ''
    in_quote = False
    for char in values_str:
        if char == "'" and (not current or current[-1] != '\\'):
            in_quote = not in_quote
        if char == ',' and not in_quote:
            values.append(current.strip())
            current = ''
        else:
            current += char
    if current:
        values.append(current.strip())
    return [parse_sql_value(v) for v in values]

def seed_groups(sql_file):
    """Extract and insert groups from backup."""
    group_inserts = []
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO groups_group' in line:
                group_inserts.append(line)

    if not group_inserts:
        print('  No group inserts found.')
        return 0

    # Parse a sample insert to get column order
    # Expected columns: id, name, location, date_created, officer_name, banking_type,
    #                  client_uuid, client_updated_at, created_at, updated_at
    created = 0
    for line in group_inserts[:20]:  # Limit to first 20 for speed
        try:
            values = extract_insert_values(line)
            if not values or len(values) < 8:
                continue

            # Map typical PostgreSQL group table columns
            group, did_create = Group.objects.get_or_create(
                name=str(values[1] or 'Group'),
                defaults={
                    'location': str(values[2] or 'Location'),
                    'date_created': values[3] if isinstance(values[3], date) else date.today(),
                    'officer_name': str(values[4] or 'Officer'),
                    'banking_type': str(values[5] or 'office')[:10],
                    'client_uuid': values[6] if isinstance(values[6], uuid.UUID) else uuid.uuid4(),
                    'client_updated_at': values[7] if isinstance(values[7], datetime) else timezone.now(),
                }
            )
            if did_create:
                created += 1
        except Exception as e:
            print(f'  Failed to parse group insert: {str(e)[:100]}')

    return created

def seed_members(sql_file):
    """Extract and insert members from backup."""
    member_inserts = []
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO members_member' in line:
                member_inserts.append(line)

    if not member_inserts:
        print('  No member inserts found.')
        return 0

    created = 0
    for line in member_inserts[:100]:  # Limit to first 100
        try:
            values = extract_insert_values(line)
            if not values or len(values) < 8:
                continue

            # Typical columns: id, group_id, member_number, name, phone, join_date,
            #                  is_active, client_uuid, client_updated_at, created_at, updated_at
            group_id = values[1]
            try:
                group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                continue

            member, did_create = Member.objects.get_or_create(
                client_uuid=values[7] if values[7] else uuid.uuid4(),
                defaults={
                    'group': group,
                    'member_number': values[2] if values[2] else None,
                    'name': str(values[3] or 'Member'),
                    'phone': str(values[4] or ''),
                    'join_date': values[5] if isinstance(values[5], date) else date.today(),
                    'is_active': bool(values[6]) if values[6] is not None else True,
                    'client_updated_at': values[8] if isinstance(values[8], datetime) else timezone.now(),
                }
            )
            if did_create:
                created += 1
        except Exception as e:
            print(f'  Failed to parse member insert: {str(e)[:100]}')

    return created

def seed_monthly_forms(sql_file):
    """Extract and insert monthly forms from backup."""
    form_inserts = []
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO finance_monthlyform' in line:
                form_inserts.append(line)

    if not form_inserts:
        print('  No monthly form inserts found.')
        return 0

    created = 0
    for line in form_inserts[:50]:  # Limit to first 50
        try:
            values = extract_insert_values(line)
            if not values or len(values) < 10:
                continue

            # Typical columns: id, group_id, month, year, status, notes, client_uuid,
            #                  client_updated_at, created_by_id, created_at, updated_at
            group_id = values[1]
            try:
                group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                continue

            form, did_create = MonthlyForm.objects.get_or_create(
                client_uuid=values[6] if values[6] else uuid.uuid4(),
                defaults={
                    'group': group,
                    'month': int(values[2]) if values[2] else 1,
                    'year': int(values[3]) if values[3] else 2026,
                    'status': str(values[4] or 'draft')[:20],
                    'notes': str(values[5] or ''),
                    'client_updated_at': values[7] if isinstance(values[7], datetime) else timezone.now(),
                }
            )
            if did_create:
                created += 1
        except Exception as e:
            print(f'  Failed to parse monthly form insert: {str(e)[:100]}')

    return created

if __name__ == '__main__':
    if not os.path.exists(SQL_FILE):
        print(f'SQL backup not found at {SQL_FILE}')
        sys.exit(1)

    print(f'Seeding from {SQL_FILE}...')
    print('Groups:', seed_groups(SQL_FILE))
    print('Members:', seed_members(SQL_FILE))
    print('Monthly Forms:', seed_monthly_forms(SQL_FILE))
    print('Done!')
