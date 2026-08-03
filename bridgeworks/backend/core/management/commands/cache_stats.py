"""
Management command to display Redis cache statistics.

Usage:
    python manage.py cache_stats
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Display Redis cache statistics (memory, hit rate, connected clients)'

    def handle(self, *args, **options):
        # Check if we're using django-redis
        backend = cache.__class__.__name__

        if backend == 'RedisCache':
            try:
                client = cache.client.get_client()
                stats = client.info()

                self.stdout.write(self.style.SUCCESS("=== Redis Cache Stats ==="))
                self.stdout.write(f"  Memory Used:      {stats.get('used_memory_human', 'N/A')}")
                self.stdout.write(f"  Peak Memory:      {stats.get('used_memory_peak_human', 'N/A')}")
                self.stdout.write(f"  Connected Clients: {stats.get('connected_clients', 'N/A')}")

                hits = stats.get('keyspace_hits', 0)
                misses = stats.get('keyspace_misses', 0)
                total = hits + misses
                hit_rate = f"{hits / total:.1%}" if total > 0 else "N/A (no requests yet)"

                self.stdout.write(f"  Hits:             {hits}")
                self.stdout.write(f"  Misses:           {misses}")
                self.stdout.write(f"  Hit Rate:         {hit_rate}")
                self.stdout.write(f"  Evicted Keys:     {stats.get('evicted_keys', 0)}")
                self.stdout.write(f"  Total Keys:       {stats.get('db0', {}).get('keys', 0)}")

                # Show BridgeWorks-specific key count
                keys = client.keys('bridgeworks:*')
                self.stdout.write(f"  BridgeWorks Cache Keys: {len(keys)}")

                self.stdout.write(self.style.SUCCESS("========================"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error connecting to Redis: {e}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"Current cache backend is '{backend}' (not Redis).\n"
                "Set CACHE_REDIS_URL or REDIS_URL env var to enable Redis caching."
            ))
