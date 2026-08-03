import os
import sys
import django

# Set up django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridgeworks_backend.settings')
django.setup()

# Monkey patch Cloudinary Storage upload to run offline and accept mock bytes
from cloudinary_storage.storage import MediaCloudinaryStorage
MediaCloudinaryStorage._upload = lambda self, name, content: {'public_id': name}

from django.contrib.auth import get_user_model
from hr.training.models import TrainingFile, TrainingPush, TrainingPushRecipient, TrainingAcknowledgement
from core.models import WorkforceMember, WorkforceDepartment
from django.core.files.base import ContentFile
from django.utils import timezone
import random

User = get_user_model()
org_id = 'janki-jewels'

# Find or create a creator/admin user for janki-jewels
creator = User.objects.filter(username='deepak').first()
if not creator:
    creator = User.objects.first()

# Create some departments if they don't exist
depts = ['Logistics', 'Operations', 'Marketing', 'HR', 'Engineering']
dept_objs = {}
for name in depts:
    obj, _ = WorkforceDepartment.objects.get_or_create(org_id=org_id, name=name)
    dept_objs[name] = obj

# Clean up existing mock users/workforce members
User.objects.filter(username__startswith='mock_emp_').delete()
User.objects.filter(email__startswith='mock_emp_').delete()
WorkforceMember.objects.filter(email__startswith='mock_emp_').delete()

# Get actual users (exclude any leftover mock ones)
actual_users = list(User.objects.exclude(username__startswith='mock_emp_').exclude(email__startswith='mock_emp_'))

# Ensure each actual user with an email is added to the users pool
users_pool = []
for u in actual_users:
    if not u.email:
        continue
    users_pool.append(u)

# If pool is empty or too small, fallback to actual users or admin/superusers
if len(users_pool) < 5:
    for u in User.objects.all():
        if u not in users_pool:
            users_pool.append(u)

# Clear existing training files/pushes for clean slate
TrainingFile.objects.filter(org_id=org_id).delete()
TrainingPush.objects.filter(org_id=org_id).delete()

# Files list from the image
files_data = [
    {
        'title': 'Onboarding handbook 2025',
        'file_name': 'onboarding_handbook_v3.pdf',
        'category': 'onboarding',
        'is_mandatory': True,
        'department_target': '',
        'expiry_date': timezone.datetime(2026, 12, 31).date(),
        'target_completion': 0.82
    },
    {
        'title': 'Anti-harassment policy',
        'file_name': 'anti_harassment_policy.pdf',
        'category': 'compliance',
        'is_mandatory': True,
        'department_target': '',
        'expiry_date': timezone.datetime(2026, 3, 31).date(),
        'target_completion': 0.91
    },
    {
        'title': 'Warehouse safety training',
        'file_name': 'wh_safety_deck.pptx',
        'category': 'compliance',
        'is_mandatory': True,
        'department_target': 'Logistics',
        'expiry_date': timezone.datetime(2026, 6, 30).date(),
        'target_completion': 0.54
    },
    {
        'title': 'Product listing SOP',
        'file_name': 'product_listing_sop_v2.docx',
        'category': 'sops',
        'is_mandatory': False,
        'department_target': 'Operations',
        'expiry_date': None,
        'target_completion': 0.38
    },
    {
        'title': 'Customer service playbook',
        'file_name': 'cs_playbook_q2.pdf',
        'category': 'skills',
        'is_mandatory': False,
        'department_target': 'Marketing',
        'expiry_date': None,
        'target_completion': 0.65
    },
    {
        'title': 'Returns & refunds process',
        'file_name': 'returns_sop_v4.docx',
        'category': 'sops',
        'is_mandatory': True,
        'department_target': 'Operations',
        'expiry_date': timezone.datetime(2026, 9, 30).date(),
        'target_completion': 0.77
    },
    {
        'title': 'Social media guidelines',
        'file_name': 'social_media_guidelines.pdf',
        'category': 'compliance',
        'is_mandatory': True,
        'department_target': 'Marketing',
        'expiry_date': timezone.datetime(2026, 11, 30).date(),
        'target_completion': 0.43
    },
    {
        'title': 'Excel for ops teams',
        'file_name': 'excel_basics_training.mp4',
        'category': 'skills',
        'is_mandatory': False,
        'department_target': 'Operations',
        'expiry_date': None,
        'target_completion': 0.29
    }
]

for fd in files_data:
    # Create file record
    tf = TrainingFile(
        org_id=org_id,
        title=fd['title'],
        category=fd['category'],
        department_target=fd['department_target'],
        is_mandatory=fd['is_mandatory'],
        expiry_date=fd['expiry_date'],
        uploaded_by=creator,
        version=3 if 'v3' in fd['file_name'] else (4 if 'v4' in fd['file_name'] else (2 if 'v2' in fd['file_name'] else 1))
    )
    tf.file.save(fd['file_name'], ContentFile(b'mock file content'))
    tf.save()
    
    # Create push
    push = TrainingPush.objects.create(
        org_id=org_id,
        training_file=tf,
        pushed_by=creator,
        is_mandatory=fd['is_mandatory'],
        target_departments=[fd['department_target']] if fd['department_target'] else []
    )
    
    # Determine recipients based on target percentages
    total_rec = 11 if fd['target_completion'] in [0.82, 0.91, 0.54] else (13 if fd['target_completion'] in [0.38, 0.77] else (20 if fd['target_completion'] == 0.65 else 14))
    if fd['target_completion'] == 0.54:
        total_rec = 13
        ack_count = 7
    elif fd['target_completion'] == 0.38:
        total_rec = 13
        ack_count = 5
    elif fd['target_completion'] == 0.77:
        total_rec = 13
        ack_count = 10
    elif fd['target_completion'] == 0.43:
        total_rec = 14
        ack_count = 6
    elif fd['target_completion'] == 0.29:
        total_rec = 14
        ack_count = 4
    else:
        ack_count = int(round(total_rec * fd['target_completion']))
        
    total_rec = min(len(users_pool), total_rec)
    ack_count = min(ack_count, total_rec)
    recipients = random.sample(users_pool, total_rec)
    for j, user in enumerate(recipients):
        is_ack = j < ack_count
        rec = TrainingPushRecipient.objects.create(
            push=push,
            user=user,
            is_acknowledged=is_ack,
            acknowledged_at=timezone.now() - timezone.timedelta(days=random.randint(1, 10)) if is_ack else None
        )
        if is_ack:
            TrainingAcknowledgement.objects.create(
                org_id=org_id,
                training_file=tf,
                user=user,
                push_recipient=rec,
                acknowledged_at=rec.acknowledged_at,
                notes="Completed."
            )

print("Database seeded successfully!")
