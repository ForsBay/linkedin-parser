"""
Работа с LinkedIn
Используются публичные (guest) API, которые сайт сам дергает при просмотре вакансий
без логина (нашел через DevTools -> Network):

  поиск:    /jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=...&location=...&start=0
  вакансия: /jobs-guest/jobs/api/jobPosting/<job_id>
  компания: /company/<slug>

Ответы приходят в виде кусков HTML, поэтому парсим через BeautifulSoup
"""
import re
import time
import random

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://www.linkedin.com'
SEARCH_URL = BASE_URL + '/jobs-guest/jobs/api/seeMoreJobPostings/search'
JOB_URL = BASE_URL + '/jobs-guest/jobs/api/jobPosting/{}'
COMPANY_URL = BASE_URL + '/company/{}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

PAGE_SIZE = 10

# LinkedIn отдает максимум ~1000 вакансий на один поиск
# Фильтры f_E / f_JT гостевой API игнорирует (проверял - выдача та же),
# а вот локация работает, поэтому большую страну разбиваем на штаты
US_STATES = [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut',
    'Delaware', 'District of Columbia', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois',
    'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts',
    'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota',
    'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina',
    'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming',
]


class LinkedInError(Exception):
    pass


class NotFoundError(LinkedInError):
    pass


def get_page(url, params=None, retries=5):
    for attempt in range(1, retries + 1):
        try:
            # без сессии: с накопленными cookies LinkedIn быстрее отдает 429
            response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f'  ошибка сети: {e}, попытка {attempt}')
            time.sleep(5 * attempt)
            continue

        if response.status_code == 200:
            return response.text
        if response.status_code in (400, 404):
            raise NotFoundError(f'{response.status_code} {url}')

        # 429 / 999 / 5xx - нас притормозили, ждем и пробуем снова
        print(f'  статус {response.status_code}, жду и пробую снова (попытка {attempt})')
        time.sleep(10 * attempt + random.random() * 5)

    raise LinkedInError(f'не удалось загрузить {url}')


def get_search_locations(country):
    locations = [country]
    if country.lower() in ('usa', 'us', 'united states'):
        for state in US_STATES:
            locations.append(f'{state}, United States')
    return locations


def search_jobs(keywords, location, start=0, extra_params=None):
    params = {'keywords': keywords, 'location': location, 'start': start}
    if extra_params:
        params.update(extra_params)
    try:
        html = get_page(SEARCH_URL, params=params)
    except NotFoundError:
        # дошли до конца выдачи
        return []
    return parse_search_page(html)


def clean_text(el):
    if el is None:
        return ''
    return ' '.join(el.get_text(' ', strip=True).split())


def get_company_slug(url):
    if not url:
        return ''
    match = re.search(r'linkedin\.com/company/([^/?#]+)', url)
    if match:
        return match.group(1)
    return ''


def parse_search_page(html):
    soup = BeautifulSoup(html, 'lxml')
    jobs = []
    for card in soup.select('li'):
        div = card.select_one('[data-entity-urn]')
        if not div:
            continue
        urn = div.get('data-entity-urn', '')
        job_id = urn.split(':')[-1]
        if not job_id.isdigit():
            continue

        link = card.select_one('a.base-card__full-link')
        url = link.get('href', '').split('?')[0] if link else ''
        if not url:
            url = f'{BASE_URL}/jobs/view/{job_id}'

        company_link = card.select_one('h4.base-search-card__subtitle a')
        company_url = company_link.get('href', '').split('?')[0] if company_link else ''

        time_el = card.select_one('time')

        jobs.append({
            'job_id': int(job_id),
            'title': clean_text(card.select_one('h3.base-search-card__title')),
            'company_name': clean_text(card.select_one('h4.base-search-card__subtitle')),
            'company_url': company_url,
            'location': clean_text(card.select_one('.job-search-card__location')),
            'url': url,
            'posted_date': time_el.get('datetime') if time_el else None,
            'salary': clean_text(card.select_one('.job-search-card__salary-info')),
            'benefits': clean_text(card.select_one('.job-posting-benefits__text')),
        })
    return jobs


def get_job_details(job_id):
    html = get_page(JOB_URL.format(job_id))
    data = parse_job_page(html)
    if not data['title']:
        # вместо вакансии пришла заглушка (например authwall)
        raise LinkedInError('пустая страница вакансии')
    return data


def parse_job_page(html):
    soup = BeautifulSoup(html, 'lxml')
    data = {}

    data['title'] = clean_text(soup.select_one('.top-card-layout__title'))

    company_link = soup.select_one('a.topcard__org-name-link')
    if company_link:
        data['company_name'] = clean_text(company_link)
        data['company_url'] = company_link.get('href', '').split('?')[0]

    location = soup.select_one('.topcard__flavor--bullet')
    data['location'] = clean_text(location)
    data['posted_time_ago'] = clean_text(soup.select_one('.posted-time-ago__text'))

    applicants = soup.select_one('.num-applicants__caption')
    if not applicants:
        applicants = soup.select_one('figcaption.num-applicants__caption')
    data['applicants'] = clean_text(applicants)

    data['salary'] = clean_text(soup.select_one('.compensation__salary'))
    data['is_closed'] = soup.select_one('.closed-job') is not None

    description = soup.select_one('.description__text .show-more-less-html__markup')
    if not description:
        description = soup.select_one('.description__text')
    if description:
        data['description_html'] = str(description)
        data['description'] = description.get_text('\n', strip=True)
    else:
        data['description_html'] = ''
        data['description'] = ''

    criteria = {}
    for item in soup.select('li.description__job-criteria-item'):
        name = clean_text(item.select_one('.description__job-criteria-subheader'))
        value = clean_text(item.select_one('.description__job-criteria-text'))
        criteria[name] = value
    data['seniority_level'] = criteria.get('Seniority level', '')
    data['employment_type'] = criteria.get('Employment type', '')
    data['industries'] = criteria.get('Industries', '')

    return data


def parse_number(text):
    digits = re.sub(r'[^\d]', '', text or '')
    if digits:
        return int(digits)
    return None


def get_company_details(slug):
    html = get_page(COMPANY_URL.format(slug))
    if 'authwall' in html[:3000] and 'about-us' not in html:
        raise LinkedInError('LinkedIn просит авторизацию (authwall)')
    return parse_company_page(html)


def parse_company_page(html):
    soup = BeautifulSoup(html, 'lxml')
    data = {}

    data['name'] = clean_text(soup.select_one('h1.top-card-layout__title'))
    data['description'] = clean_text(soup.select_one('[data-test-id="about-us__description"]'))

    def about_field(name):
        el = soup.select_one(f'[data-test-id="about-us__{name}"] dd')
        return clean_text(el)

    data['website'] = about_field('website').split(' External link')[0]
    data['industry'] = about_field('industry')
    data['company_size'] = about_field('size')
    data['headquarters'] = about_field('headquarters')
    data['company_type'] = about_field('organizationType')
    data['founded'] = about_field('foundedOn')
    data['specialties'] = about_field('specialties')

    logo = soup.select_one('img.top-card-layout__entity-image')
    data['logo_url'] = ''
    if logo:
        data['logo_url'] = logo.get('data-delayed-url') or logo.get('src') or ''

    data['followers'] = None
    subline = clean_text(soup.select_one('.top-card-layout__first-subline'))
    match = re.search(r'([\d,]+)\s+followers', subline)
    if match:
        data['followers'] = parse_number(match.group(1))

    data['employees_on_linkedin'] = None
    employees = clean_text(soup.select_one('[data-test-id="view-all-employees-cta"]'))
    match = re.search(r'([\d,]+)\s+employees', employees)
    if match:
        data['employees_on_linkedin'] = parse_number(match.group(1))

    return data
