"""
One-off / manual tick cleanup:  python manage.py prune_ticks [--keep 10000]
The price engine already does this automatically; this is for manual runs.
"""
from django.core.management.base import BaseCommand, CommandError

from trading.tick_pruning import prune_ticks_batch


class Command(BaseCommand):
    help = "Delete old ticks, keeping the newest N per instrument."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=10_000, help="Ticks to keep per instrument (min 1000).")

    def handle(self, *args, **options):
        keep = options["keep"]
        if keep < 1000:
            # The chart endpoint serves up to 500 ticks, so never go below a safe margin.
            raise CommandError("--keep must be at least 1000.")
        total = 0
        while True:
            deleted = prune_ticks_batch(keep_latest=keep)
            if not deleted:
                break
            total += deleted
            self.stdout.write(f"Deleted {total} so far...")
        self.stdout.write(self.style.SUCCESS(f"Done. Deleted {total} old ticks."))