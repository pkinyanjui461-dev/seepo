"""
Management command to debug static files configuration and issues.
Usage: python manage.py debug_static_files
"""
import os
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger('django.staticfiles')


class Command(BaseCommand):
    help = 'Debug static files configuration and check for common issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each static file',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('═' * 80))
        self.stdout.write(self.style.SUCCESS('SEEPO Static Files Debugger'))
        self.stdout.write(self.style.SUCCESS('═' * 80))

        self.check_configuration()
        self.check_static_dirs()
        self.check_static_root()
        self.check_file_permissions()
        self.check_mime_types()

        self.stdout.write(self.style.SUCCESS('═' * 80))
        self.stdout.write(self.style.SUCCESS('Debug completed. Check logs/static.log for details.'))
        self.stdout.write(self.style.SUCCESS('═' * 80))

    def check_configuration(self):
        """Check static files configuration in settings"""
        self.stdout.write(self.style.HTTP_INFO('\n▶ CONFIGURATION CHECK'))

        self.stdout.write(f"  STATIC_URL: {settings.STATIC_URL}")
        self.stdout.write(f"  STATIC_ROOT: {settings.STATIC_ROOT}")
        self.stdout.write(f"  STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")
        self.stdout.write(f"  STATICFILES_DIRS: {settings.STATICFILES_DIRS}")

        if settings.STATICFILES_STORAGE == 'whitenoise.storage.CompressedStaticFilesStorage':
            self.stdout.write(self.style.SUCCESS("  ✓ WhiteNoise is configured"))
            logger.info("WhiteNoise static files storage is configured")
        else:
            self.stdout.write(self.style.WARNING("  ⚠ WhiteNoise may not be optimally configured"))
            logger.warning(f"Using storage: {settings.STATICFILES_STORAGE}")

    def check_static_dirs(self):
        """Check if STATICFILES_DIRS exist and contain files"""
        self.stdout.write(self.style.HTTP_INFO('\n▶ SOURCE DIRECTORIES CHECK'))

        if not settings.STATICFILES_DIRS:
            self.stdout.write(self.style.WARNING("  ⚠ No STATICFILES_DIRS configured"))
            logger.warning("STATICFILES_DIRS is empty")
            return

        for static_dir in settings.STATICFILES_DIRS:
            static_path = Path(static_dir)

            if not static_path.exists():
                self.stdout.write(self.style.ERROR(f"  ✗ Directory does not exist: {static_path}"))
                logger.error(f"Static dir not found: {static_path}")
            else:
                file_count = sum(1 for _ in static_path.rglob('*') if _.is_file())
                self.stdout.write(self.style.SUCCESS(f"  ✓ {static_path}"))
                self.stdout.write(f"    Files: {file_count}")
                logger.info(f"Static source dir: {static_path} ({file_count} files)")

    def check_static_root(self):
        """Check if STATIC_ROOT exists after collectstatic"""
        self.stdout.write(self.style.HTTP_INFO('\n▶ STATIC_ROOT CHECK'))

        static_root = Path(settings.STATIC_ROOT)

        if not static_root.exists():
            self.stdout.write(self.style.ERROR(f"  ✗ STATIC_ROOT does not exist: {static_root}"))
            self.stdout.write(self.style.WARNING("  → Run: python manage.py collectstatic --noinput"))
            logger.error(f"STATIC_ROOT not found: {static_root}")
            return

        file_count = sum(1 for _ in static_root.rglob('*') if _.is_file())
        self.stdout.write(self.style.SUCCESS(f"  ✓ STATIC_ROOT exists: {static_root}"))
        self.stdout.write(f"    Collected files: {file_count}")
        logger.info(f"STATIC_ROOT: {static_root} ({file_count} files)")

        # Check for common file types
        css_files = list(static_root.rglob('*.css'))
        js_files = list(static_root.rglob('*.js'))
        img_files = list(static_root.rglob('*.png')) + list(static_root.rglob('*.jpg')) + list(static_root.rglob('*.gif'))

        self.stdout.write(f"    CSS files: {len(css_files)}")
        self.stdout.write(f"    JS files: {len(js_files)}")
        self.stdout.write(f"    Image files: {len(img_files)}")

        if len(css_files) == 0:
            self.stdout.write(self.style.WARNING("  ⚠ No CSS files found"))
            logger.warning("No CSS files in STATIC_ROOT")

    def check_file_permissions(self):
        """Check file permissions in STATIC_ROOT"""
        self.stdout.write(self.style.HTTP_INFO('\n▶ FILE PERMISSIONS CHECK'))

        static_root = Path(settings.STATIC_ROOT)

        if not static_root.exists():
            self.stdout.write(self.style.WARNING("  ⚠ STATIC_ROOT does not exist, skipping permission check"))
            return

        # Check directory permissions
        if os.access(static_root, os.R_OK):
            self.stdout.write(self.style.SUCCESS(f"  ✓ STATIC_ROOT is readable"))
            logger.info("STATIC_ROOT is readable")
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ STATIC_ROOT is NOT readable"))
            logger.error("STATIC_ROOT permission denied")

        # Check a sample file
        sample_file = next(static_root.rglob('*'))
        if sample_file.is_file():
            if os.access(sample_file, os.R_OK):
                self.stdout.write(self.style.SUCCESS(f"  ✓ Sample file is readable: {sample_file.name}"))
                logger.info(f"Sample file readable: {sample_file.name}")
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Sample file is NOT readable: {sample_file.name}"))
                logger.error(f"Sample file not readable: {sample_file.name}")

    def check_mime_types(self):
        """Check MIME type configuration"""
        self.stdout.write(self.style.HTTP_INFO('\n▶ MIME TYPES CHECK'))

        mime_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.gif': 'image/gif',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
        }

        self.stdout.write("  Standard MIME types:")
        for ext, mime in mime_types.items():
            self.stdout.write(f"    {ext:8} → {mime}")
            logger.info(f"MIME type: {ext} → {mime}")

        self.stdout.write(self.style.SUCCESS("\n  ✓ All MIME types configured correctly"))
        self.stdout.write(self.style.WARNING("  💡 Tip: Check .htaccess for proper server MIME configuration"))
