"""
Management command to load bakery data from dessert.json into database

Usage:
    python manage.py load_bakeries
    python manage.py load_bakeries --file path/to/custom.json
    python manage.py load_bakeries --clear  # 기존 데이터 삭제 후 로드
"""

import json
from django.core.management.base import BaseCommand
from chatbot.models import Bakery


class Command(BaseCommand):
    help = 'Load bakery data from dessert_en.json into database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='./chatbot/dessert_en.json',
            help='Path to JSON file (default: ./chatbot/dessert_en.json)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing bakery data before loading'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        clear_existing = options['clear']

        # 기존 데이터 삭제
        if clear_existing:
            count = Bakery.objects.count()
            Bakery.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Deleted {count} existing bakeries')
            )

        

        # JSON 파일 로드
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bakeries_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'File not found: {file_path}')
            )
            return
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Invalid JSON: {e}')
            )
            return

        self.stdout.write(f'Loading {len(bakeries_data)} bakeries...')

        created_count = 0
        updated_count = 0
        error_count = 0

        for idx, data in enumerate(bakeries_data, 1):
            try:

                # keywords 리스트를 쉼표로 구분된 문자열로 변환
                keywords_list = data.get('keywords', [])
                keywords_str = ', '.join(keywords_list) if isinstance(keywords_list, list) else ''

                # 빵집 이름으로 기존 데이터 확인 (중복 방지)
                bakery, created = Bakery.objects.update_or_create(
                    name=data.get('name', ''),
                    defaults={
                        'category': data.get('category', ''),
                        'district': data.get('district', ''),
                        'road_address': data.get('road_address', ''),
                        'jibun_address': data.get('jibun_address', ''),
                        'phone': data.get('phone', ''),
                        'business_hours_raw': data.get('business_hours_raw', ''),
                        'monday': data.get('monday', ''),
                        'tuesday': data.get('tuesday', ''),
                        'wednesday': data.get('wednesday', ''),
                        'thursday': data.get('thursday', ''),
                        'friday': data.get('friday', ''),
                        'saturday': data.get('saturday', ''),
                        'sunday': data.get('sunday', ''),
                        'slug_en': data.get('slug_en', ''),
                        'url': data.get('url', ''),
                        'latitude': data.get('latitude') or None,
                        'longitude': data.get('longitude') or None,
                        'rate': data.get('rating', ''),
                        'keywords': keywords_str,
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # 진행 상황 출력 (100개마다)
                if idx % 100 == 0:
                    self.stdout.write(f'  Processed {idx}/{len(bakeries_data)}...')

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error processing bakery #{idx}: {e}')
                )

        # 결과 요약
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Loading complete!\n'
                f'  - Created: {created_count}\n'
                f'  - Updated: {updated_count}\n'
                f'  - Errors: {error_count}\n'
                f'  - Total: {Bakery.objects.count()} bakeries in database'
            )
        )