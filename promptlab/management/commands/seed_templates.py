from django.core.management.base import BaseCommand

from promptlab.seed_data import run_seed


class Command(BaseCommand):
    help = "Seed the Prompt Library with curated templates (idempotent)."

    def handle(self, *args, **options):
        created, updated = run_seed(verbose=False)
        self.stdout.write(self.style.SUCCESS(
            f"Prompt Library seeded: {created} created, {updated} already present."))
