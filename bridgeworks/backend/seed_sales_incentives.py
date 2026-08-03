import os
import django
import random
from datetime import timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridgeworks_backend.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import ShopCredentials
from core.models.sales import (
    SalesRepresentative, SalesActivity, SalesActivityProduct,
    IncentiveRule, IncentiveRecord
)

User = get_user_model()

def seed_data():
    print("Starting sales & incentives seeding...")
    
    # 1. Resolve Shop & Users
    shop = ShopCredentials.objects.first()
    if not shop:
        print("Creating a default ShopCredentials...")
        shop = ShopCredentials.objects.create(
            shop_url="dummy-shop.myshopify.com",
            access_token="dummy_token",
            organization_id="ORG001"
        )
    
    users = list(User.objects.filter(is_active=True))
    if not users:
        print("Creating a default user...")
        default_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        users = [default_user]
    
    # Clean up existing data to prevent duplicate primary/unique constraints on repeat runs
    print("Cleaning up old sales representative and incentive data...")
    IncentiveRecord.objects.all().delete()
    IncentiveRule.objects.all().delete()
    SalesActivityProduct.objects.all().delete()
    SalesActivity.objects.all().delete()
    SalesRepresentative.objects.all().delete()

    # 2. Seed 5 Sales Representatives
    designations = ['Sales Executive', 'Senior Sales Executive', 'Key Account Manager', 'BD Associate', 'Territory Manager']
    departments = ['Retail Sales', 'Corporate Accounts', 'Wholesale Sales', 'Direct Sales', 'Institutional Sales']
    names = ['John Doe', 'Jane Smith', 'Alice Johnson', 'Robert Lee', 'Emily Davis']
    
    reps = []
    manager = None
    
    for i in range(5):
        emp_id = f"EMP{1000 + i}"
        email = f"{names[i].lower().replace(' ', '.')}@example.com"
        phone = f"+91987654321{i}"
        
        # Link to a Django user if available (wrap around if less than 5 users)
        user_link = users[i % len(users)]
        
        rep = SalesRepresentative.objects.create(
            shop=shop,
            employee_id=emp_id,
            user=user_link,
            full_name=names[i],
            email=email,
            phone=phone,
            designation=designations[i],
            department=departments[i],
            reporting_manager=manager,  # First rep has no manager, others report to previous
            status='active'
        )
        reps.append(rep)
        manager = rep  # Set current rep as manager for next reps to create a hierarchy

    print(f"Created {len(reps)} Sales Representatives.")

    # 3. Seed 5 Incentive Rules
    rules_data = [
        {"name": "Standard Product 5% Commission", "type": "percentage", "pct": 5.00, "fixed": None, "target": None, "bonus": None},
        {"name": "Premium Product 10% Commission", "type": "percentage", "pct": 10.00, "fixed": None, "target": None, "bonus": None},
        {"name": "Flat Visit Bonus", "type": "fixed", "pct": None, "fixed": 250.00, "target": None, "bonus": None},
        {"name": "Silver Monthly Target Bonus", "type": "target_bonus", "pct": None, "fixed": None, "target": 50000.00, "bonus": 5000.00},
        {"name": "Gold Monthly Target Bonus", "type": "target_bonus", "pct": None, "fixed": None, "target": 100000.00, "bonus": 12000.00},
    ]
    
    rules = []
    for r in rules_data:
        rule = IncentiveRule.objects.create(
            shop=shop,
            rule_name=r["name"],
            rule_type=r["type"],
            percentage_value=r["pct"],
            fixed_amount=r["fixed"],
            target_amount=r["target"],
            bonus_amount=r["bonus"],
            status='active'
        )
        rules.append(rule)
        
    print(f"Created {len(rules)} Incentive Rules.")

    # 4. Seed 20 Sales Activities with 1-3 Products
    customers = [
        ('Apex Industries', 'Corporate'),
        ('Beta Retailers', 'Retail'),
        ('Gamma Corp', 'Corporate'),
        ('Delta Enterprises', 'Wholesale'),
        ('Omega Ventures', 'Corporate'),
        ('Sigma Distributors', 'Wholesale'),
        ('Zenith Stores', 'Retail'),
        ('Infinity Trading', 'Wholesale'),
        ('Pinnacle Ltd', 'Corporate'),
        ('Summit Wholesale', 'Wholesale')
    ]
    
    products_list = [
        ('PROD-001', 'Standard Office Chair', 1200.00),
        ('PROD-002', 'Premium Ergonomic Desk', 4500.00),
        ('PROD-003', 'LED Task Light', 450.00),
        ('PROD-004', 'Steel Filing Cabinet', 2200.00),
        ('PROD-005', 'Conference Speakerphone', 8900.00)
    ]
    
    statuses = ['draft', 'submitted', 'approved', 'rejected']
    activities = []
    
    for i in range(20):
        rep = random.choice(reps)
        cust_name, cust_type = random.choice(customers)
        status = random.choice(statuses)
        
        # Random date in last 30 days
        visit_date = timezone.now().date() - timedelta(days=random.randint(0, 30))
        
        activity = SalesActivity.objects.create(
            sales_rep=rep,
            customer_name=f"{cust_name} #{random.randint(1, 100)}",
            customer_type=cust_type,
            location=random.choice(['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Pune']),
            visit_date=visit_date,
            remarks=f"Discussed product requirements for office upgrade. Status is {status}.",
            status=status,
            submitted_at=timezone.now() if status != 'draft' else None,
            approved_at=timezone.now() if status == 'approved' else None,
            approved_by=random.choice(users) if status == 'approved' else None
        )
        
        # Add 1 to 3 products
        num_products = random.randint(1, 3)
        selected_prods = random.sample(products_list, num_products)
        
        for prod_id, prod_name, unit_price in selected_prods:
            qty = random.randint(1, 10)
            total = qty * unit_price
            
            SalesActivityProduct.objects.create(
                sales_activity=activity,
                product_id=prod_id,
                product_name=prod_name,
                quantity=qty,
                unit_price=unit_price,
                total_amount=total
            )
            
        activities.append(activity)

    print(f"Created {len(activities)} Sales Activities.")

    # 5. Seed 20 Incentive Records
    record_statuses = ['pending', 'approved', 'paid']
    for i in range(20):
        rep = random.choice(reps)
        activity = random.choice(activities)
        rule = random.choice(rules)
        status = random.choice(record_statuses)
        
        # Calculate random incentive amount between 100 and 5000
        incentive_amount = round(random.uniform(100.00, 5000.00), 2)
        
        IncentiveRecord.objects.create(
            sales_rep=rep,
            sales_activity=activity,
            rule=rule,
            incentive_amount=incentive_amount,
            status=status,
            calculated_at=timezone.now() - timedelta(days=random.randint(0, 15)),
            paid_at=timezone.now() if status == 'paid' else None
        )

    print("Created 20 Incentive Records.")
    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed_data()
