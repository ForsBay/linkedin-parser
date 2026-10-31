import time
import random
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs import linkedin
from jobs.models import SearchQuery, Job


class Command(BaseCommand):
    help = 'Часть 1: поиск вакансий по активным поисковым запросам и сохранение в БД'

    def add_arguments(self, parser):
        parser.add_argument('--query-id', type=int, help='запустить только один запрос по id')
        parser.add_argument('--delay', type=float, default=1.0, help='пауза между запросами (сек)')
        parser.add_argument('--no-split', action='store_true',
                            help='не разбивать страну на регионы (будет максимум ~1000 вакансий)')

    def handle(self, *args, **options):
        queries = SearchQuery.objects.filter(is_active=True)
        if options['query_id']:
            queries = SearchQuery.objects.filter(id=options['query_id'])

        if not queries.exists():
            self.stdout.write('Нет активных поисковых запросов. Добавьте их в админке')
            return

        for query in queries:
            self.stdout.write(f'=== Запрос: {query} ===')
            try:
                self.run_query(query, options)
                query.last_error = ''
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка в запросе {query}: {e}'))
                query.last_error = str(e)
            query.jobs_found = query.jobs.count()
            query.last_run_at = timezone.now()
            query.save()
            self.stdout.write(self.style.SUCCESS(f'Всего вакансий по запросу {query}: {query.jobs_found}'))

    def run_query(self, query, options):
        if options['no_split']:
            locations = [query.country]
        else:
            locations = linkedin.get_search_locations(query.country)

        failed = []
        for location in locations:
            try:
                self.search_location(query, location, options)
            except linkedin.LinkedInError as e:
                # сбой одной локации не останавливает остальные
                self.stdout.write(self.style.ERROR(f'{location}: {e}'))
                failed.append(location)

        if failed:
            raise linkedin.LinkedInError('не загрузились локации: ' + ', '.join(failed))

    def search_location(self, query, location, options):
        start = 0
        new_count = 0
        while True:
            cards = linkedin.search_jobs(query.keywords, location, start)
            if not cards:
                break

            for card in cards:
                if self.save_job(card, query):
                    new_count += 1

            start += linkedin.PAGE_SIZE
            if start >= 1000:
                # дальше LinkedIn все равно отдает 400
                break
            time.sleep(options['delay'] + random.random())

        self.stdout.write(f'{location}: просмотрено {start}, новых {new_count}')

    def save_job(self, card, query):
        posted_date = None
        if card['posted_date']:
            try:
                posted_date = date.fromisoformat(card['posted_date'])
            except ValueError:
                pass

        job, created = Job.objects.get_or_create(
            job_id=card['job_id'],
            defaults={
                'title': card['title'][:500],
                'company_name': card['company_name'][:255],
                'company_url': card['company_url'][:500],
                'location': card['location'][:255],
                'url': card['url'][:500],
                'posted_date': posted_date,
                'salary': card['salary'][:255],
                'benefits': card['benefits'][:255],
            }
        )
        job.search_queries.add(query)
        return created
