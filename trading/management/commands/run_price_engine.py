"""
Run the synthetic price engine as a standalone long-running process.

Usage:
    python manage.py run_price_engine

This must run alongside the Daphne ASGI server (which serves HTTP +
WebSocket traffic) — it's a separate process that only generates ticks
and pushes them through the same Redis channel layer Daphne's consumers
are listening on. In production this would run under something like
supervisord or a separate worker dyno/container.
"""
import asyncio

from django.core.management.base import BaseCommand

from trading.engine import run_all_engines


class Command(BaseCommand):
    help = "Runs the synthetic price tick generator for all active market instruments."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting price engine — Ctrl+C to stop."))
        try:
            asyncio.run(run_all_engines())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Price engine stopped."))