import time
import random
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from jobs import linkedin
from jobs.models import Job, Company

MAX_ATTEMPTS = 3


class Command(BaseCommand):
    help = 'Часть 2: сбор полной информации о вакансиях и компаниях, сохраненных на этапе поиска'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='сколько вакансий обработать (0 - все)')
        parser.add_argument('--workers', type=int, default=3, help='количество потоков')
        parser.add_argument('--delay', type=float, default=1.0, help='пауза между запросами (сек)')
        parser.add_argument('--retry-errors', action='store_true',
                            help='повторить вакансии с ошибкой, даже если попытки закончились')

    def handle(self, *args, **options):
        self.delay = options['delay']

        jobs = Job.objects.filter(Q(status='new') | Q(status='error', attempts__lt=MAX_ATTEMPTS))
        if options['retry_errors']:
            jobs = Job.objects.filter(status__in=['new', 'error'])
        job_ids = list(jobs.order_by('id').values_list('id', flat=True))
        if options['limit']:
            job_ids = job_ids[:options['limit']]

        total = len(job_ids)
        self.stdout.write(f'Вакансий для обработки: {total}')

        done = 0
        errors = 0
        with ThreadPoolExecutor(max_workers=options['workers']) as executor:
            for ok in executor.map(self.process_job, job_ids):
                if ok:
                    done += 1
                else:
                    errors += 1
                if (done + errors) % 50 == 0:
                    self.stdout.write(f'обработано {done + errors}/{total}, ошибок {errors}')

        self.stdout.write(self.style.SUCCESS(f'Готово. Успешно: {done}, ошибок: {errors}'))

        # повторяем компании, которые не скачались раньше
        companies = Company.objects.filter(status__in=['new', 'error'])
        self.stdout.write(f'Компаний для повторной обработки: {companies.count()}')
        for company in companies:
            self.update_company(company)
        self.stdout.write(self.style.SUCCESS('Компании обработаны'))

    def process_job(self, pk):
        try:
            job = Job.objects.get(pk=pk)
            job.attempts += 1
            try:
                data = linkedin.get_job_details(job.job_id)
                self.update_job(job, data)
                job.company = self.get_company(job.company_url, job.company_name)
                job.status = 'done'
                job.error_message = ''
                job.details_parsed_at = timezone.now()
                ok = True
            except Exception as e:
                job.status = 'error'
                job.error_message = str(e)[:1000]
                print(f'ошибка у вакансии {job.job_id}: {e}')
                ok = False
            job.save()
            time.sleep(self.delay + random.random())
            return ok
        finally:
            # каждый поток открывает свое соединение с БД, закрываем его
            connection.close()

    def update_job(self, job, data):
        if data.get('title'):
            job.title = data['title'][:500]
        if data.get('company_name'):
            job.company_name = data['company_name'][:255]
        if data.get('company_url'):
            job.company_url = data['company_url'][:500]
        if data.get('location'):
            job.location = data['location'][:255]
        if data.get('salary'):
            job.salary = data['salary'][:255]

        job.description = data['description']
        job.description_html = data['description_html']
        job.seniority_level = data['seniority_level'][:255]
        job.employment_type = data['employment_type'][:255]
        job.industries = data['industries'][:500]
        job.applicants = data['applicants'][:100]
        job.posted_time_ago = data['posted_time_ago'][:100]
        job.is_closed = data['is_closed']

    def get_company(self, company_url, company_name):
        slug = linkedin.get_company_slug(company_url)
        if not slug:
            return None

        company, created = Company.objects.get_or_create(
            slug=slug,
            defaults={'name': company_name[:255], 'url': company_url[:500]},
        )
        if company.status == 'done':
            return company

        self.update_company(company)
        return company

    def update_company(self, company):
        try:
            data = linkedin.get_company_details(company.slug)
            if data['name']:
                company.name = data['name'][:255]
            company.description = data['description']
            company.website = data['website'][:500]
            company.industry = data['industry'][:255]
            company.company_size = data['company_size'][:255]
            company.headquarters = data['headquarters'][:255]
            company.company_type = data['company_type'][:255]
            company.founded = data['founded'][:50]
            company.specialties = data['specialties']
            company.logo_url = data['logo_url'][:1000]
            company.followers = data['followers']
            company.employees_on_linkedin = data['employees_on_linkedin']
            company.status = 'done'
            company.error_message = ''
        except Exception as e:
            # ошибка компании не ломает вакансию, компанию добираем в конце запуска
            company.status = 'error'
            company.error_message = str(e)[:1000]
            print(f'ошибка у компании {company.slug}: {e}')
        company.save()
        time.sleep(self.delay)
