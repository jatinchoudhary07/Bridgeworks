from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.models import ChatMessage


User = get_user_model()


def _get_org_id_for_user(user):
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    try:
        return user.team_settings.organization.organization_id
    except Exception:
        return None


def _org_member_ids(org_id, sender_id):
    member_ids = set(
        User.objects.filter(
            team_settings__organization__organization_id=org_id,
            is_active=True,
        ).values_list('id', flat=True)
    )
    member_ids.discard(sender_id)
    return member_ids


class Command(BaseCommand):
    help = 'Backfill and normalize ChatMessage.is_broadcast for historical messages.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing to DB.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        updated_true = 0
        updated_false = 0
        skipped = 0

        queryset = ChatMessage.objects.select_related('sender').prefetch_related('recipient_entries').all()

        for message in queryset.iterator(chunk_size=500):
            sender = message.sender
            org_id = _get_org_id_for_user(sender)
            if not org_id:
                skipped += 1
                continue

            expected_recipient_ids = _org_member_ids(org_id, sender.id)
            actual_recipient_ids = set(message.recipient_entries.values_list('recipient_id', flat=True))
            should_be_broadcast = (
                message.is_event or (
                    actual_recipient_ids == expected_recipient_ids and len(expected_recipient_ids) >= 2
                )
            )

            if message.is_broadcast != should_be_broadcast:
                if not dry_run:
                    message.is_broadcast = should_be_broadcast
                    message.save(update_fields=['is_broadcast'])

                if should_be_broadcast:
                    updated_true += 1
                else:
                    updated_false += 1

        mode = 'DRY RUN' if dry_run else 'APPLIED'
        self.stdout.write(self.style.SUCCESS(
            f'[{mode}] broadcast=True updated: {updated_true}, broadcast=False updated: {updated_false}, skipped: {skipped}'
        ))