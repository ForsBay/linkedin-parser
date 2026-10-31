import csv

from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from jobs.models import Job

COLUMNS = [
    ('job_id', lambda j: j.job_id),
    ('title', lambda j: j.title),
    ('url', lambda j: j.url),
    ('location', lambda j: j.location),
    ('posted_date', lambda j: j.posted_date.isoformat() if j.posted_date else ''),
    ('posted_time_ago', lambda j: j.posted_time_ago),
    ('seniority_level', lambda j: j.seniority_level),
    ('employment_type', lambda j: j.employment_type),
    ('industries', lambda j: j.industries),
    ('salary', lambda j: j.salary),
    ('applicants', lambda j: j.applicants),
    ('benefits', lambda j: j.benefits),
    ('is_closed', lambda j: j.is_closed),
    ('description', lambda j: j.description),
    ('search_queries', lambda j: '; '.join(str(q) for q in j.search_queries.all())),
    ('status', lambda j: j.status),
    ('company_name', lambda j: j.company_name),
    ('company_url', lambda j: j.company_url),
    ('company_website', lambda j: j.company.website if j.company else ''),
    ('company_industry', lambda j: j.company.industry if j.company else ''),
    ('company_size', lambda j: j.company.company_size if j.company else ''),
    ('company_headquarters', lambda j: j.company.headquarters if j.company else ''),
    ('company_type', lambda j: j.company.company_type if j.company else ''),
    ('company_founded', lambda j: j.company.founded if j.company else ''),
    ('company_specialties', lambda j: j.company.specialties if j.company else ''),
    ('company_followers', lambda j: j.company.followers if j.company else ''),
    ('company_employees_on_linkedin', lambda j: j.company.employees_on_linkedin if j.company else ''),
    ('company_description', lambda j: j.company.description if j.company else ''),
]


class Command(BaseCommand):
    help = 'Выгрузка вакансий вместе с компаниями в CSV или Excel'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='jobs.csv', help='файл: jobs.csv или jobs.xlsx')
        parser.add_argument('--only-done', action='store_true', help='только обработанные вакансии')

    def handle(self, *args, **options):
        jobs = Job.objects.select_related('company').prefetch_related('search_queries').order_by('id')
        if options['only_done']:
            jobs = jobs.filter(status='done')

        output = options['output']
        header = [name for name, _ in COLUMNS]

        if output.endswith('.xlsx'):
            wb = Workbook()
            ws = wb.active
            ws.title = 'jobs'
            ws.append(header)
            for job in jobs.iterator(chunk_size=1000):
                row = [func(job) for _, func in COLUMNS]
                # excel не принимает некоторые спецсимволы и больше 32767 символов в ячейке
                row = [ILLEGAL_CHARACTERS_RE.sub('', v)[:32000] if isinstance(v, str) else v for v in row]
                ws.append(row)
            wb.save(output)
        else:
            with open(output, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for job in jobs.iterator(chunk_size=1000):
                    writer.writerow([func(job) for _, func in COLUMNS])

        self.stdout.write(self.style.SUCCESS(f'Выгружено {jobs.count()} вакансий в {output}'))
