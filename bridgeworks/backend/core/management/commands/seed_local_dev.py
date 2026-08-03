"""
Management command: seed_local_dev
===================================
Creates a local admin user + shop credentials + org so all API views
have a fully authenticated context without requiring a login flow.

Usage:
    python manage.py seed_local_dev

Safe to run multiple times (idempotent).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

LOCAL_EMAIL = "admin@local.dev"
LOCAL_PASSWORD = "localdev123"
LOCAL_ORG_ID = "local-org-001"
LOCAL_SHOP_NAME = "Local Dev Shop"
LOCAL_SHOP_URL = "local.myshopify.com"


class Command(BaseCommand):
    help = "Seed a local dev admin user and shop/org for development without login"

    def handle(self, *args, **options):
        self.stdout.write("Seeding local dev data...")

        # 1. Create or get the admin user
        user, created = User.objects.get_or_create(
            email=LOCAL_EMAIL,
            defaults={
                "username": "jatin_choudhary",
                "first_name": "Jatin",
                "last_name": "Choudhary",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if not created:
            user.first_name = "Jatin"
            user.last_name = "Choudhary"
            user.username = "jatin_choudhary"
            user.save()
            self.stdout.write(f"  Updated user: {LOCAL_EMAIL} -> Jatin Choudhary")
        else:
            user.set_password(LOCAL_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  Created user: {LOCAL_EMAIL} -> Jatin Choudhary"))

        # 2. Create or get ShopCredentials (org anchor)
        try:
            from core.models import ShopCredentials
            shop, shop_created = ShopCredentials.objects.get_or_create(
                owner=user,
                defaults={
                    "organization_id": LOCAL_ORG_ID,
                    "store_name": LOCAL_SHOP_NAME,
                    "store_url": LOCAL_SHOP_URL,
                },
            )
            if shop_created:
                self.stdout.write(self.style.SUCCESS(f"  Created ShopCredentials (org_id={LOCAL_ORG_ID})"))
            else:
                self.stdout.write(f"  ShopCredentials already exists (org_id={shop.organization_id})")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Could not create ShopCredentials: {e}"))

        # 3. Ensure Site #1 exists (allauth requirement)
        try:
            from django.contrib.sites.models import Site
            Site.objects.get_or_create(id=1, defaults={"domain": "localhost", "name": "Local Dev"})
            self.stdout.write("  Site #1 ready")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Could not set Site: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Local dev seed complete!"))
        self.stdout.write(f"   Email:    {LOCAL_EMAIL}")
        self.stdout.write(f"   Password: {LOCAL_PASSWORD}")
        self.stdout.write(f"   Org ID:   {LOCAL_ORG_ID}")
