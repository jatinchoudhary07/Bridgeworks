"""
Management command: python manage.py setup_local

Idempotent local-dev bootstrap that:
  1. Ensures the django.contrib.sites Site record (id=1) points to localhost.
  2. Creates a superuser account so you can reach /admin/ without Google OAuth.
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Bootstrap local development environment (Site record + superuser)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="admin@local.dev",
            help="Superuser email (default: admin@local.dev)",
        )
        parser.add_argument(
            "--password",
            default="admin",
            help="Superuser password (default: admin)",
        )

    def handle(self, *args, **options):
        # 1. Fix the Site record so allauth uses localhost
        try:
            from django.contrib.sites.models import Site
            site, created = Site.objects.update_or_create(
                id=1,
                defaults={"domain": "localhost:8000", "name": "BridgeWorks Local"},
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{verb} Site: {site.domain}"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Could not update Site: {exc}"))

        # 2. Create superuser if it doesn't exist
        email = options["email"]
        password = options["password"]
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"Superuser {email!r} already exists — skipped"))
        else:
            username = email.split("@")[0]
            try:
                User.objects.create_superuser(username=username, email=email, password=password)
            except TypeError:
                # Custom user model may not accept username
                User.objects.create_superuser(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created superuser: {email} / {password}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Local setup complete!"))
        google_id = os.getenv("GOOGLE_CLIENT_ID", "")
        if not google_id:
            self.stdout.write(
                self.style.WARNING(
                    "\nGoogle OAuth is NOT configured.\n"
                    "Fill in GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env\n"
                    "then restart the server.  See the comment block in that file for\n"
                    "step-by-step instructions on creating credentials in Google Cloud Console."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Google OAuth client ID found: {google_id[:12]}..."))
