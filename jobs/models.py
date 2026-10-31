from django.db import models


class SearchQuery(models.Model):
    keywords = models.CharField('Поисковый запрос', max_length=255)
    country = models.CharField('Страна', max_length=255)
    is_active = models.BooleanField('Активен', default=True)
    jobs_found = models.IntegerField('Найдено вакансий', default=0)
    last_run_at = models.DateTimeField('Последний запуск', null=True, blank=True)
    last_error = models.TextField('Последняя ошибка', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Поисковый запрос'
        verbose_name_plural = 'Поисковые запросы'
        unique_together = ('keywords', 'country')

    def __str__(self):
        return f'{self.keywords} ({self.country})'


class Company(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('done', 'Обработана'),
        ('error', 'Ошибка'),
    ]

    slug = models.CharField('Slug в LinkedIn', max_length=255, unique=True)
    name = models.CharField('Название', max_length=255, blank=True)
    url = models.URLField('Ссылка LinkedIn', max_length=500, blank=True)
    logo_url = models.URLField('Логотип', max_length=1000, blank=True)
    description = models.TextField('Описание', blank=True)
    website = models.CharField('Сайт', max_length=500, blank=True)
    industry = models.CharField('Индустрия', max_length=255, blank=True)
    company_size = models.CharField('Размер компании', max_length=255, blank=True)
    headquarters = models.CharField('Штаб-квартира', max_length=255, blank=True)
    company_type = models.CharField('Тип', max_length=255, blank=True)
    founded = models.CharField('Основана', max_length=50, blank=True)
    specialties = models.TextField('Специализации', blank=True)
    followers = models.IntegerField('Подписчики', null=True, blank=True)
    employees_on_linkedin = models.IntegerField('Сотрудников в LinkedIn', null=True, blank=True)

    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    error_message = models.TextField('Ошибка', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'

    def __str__(self):
        return self.name or self.slug


class Job(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('done', 'Обработана'),
        ('error', 'Ошибка'),
    ]

    job_id = models.BigIntegerField('ID в LinkedIn', unique=True)
    search_queries = models.ManyToManyField(SearchQuery, related_name='jobs', blank=True,
                                            verbose_name='Поисковые запросы')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='jobs', verbose_name='Компания')

    # данные из поиска
    title = models.CharField('Название', max_length=500)
    company_name = models.CharField('Компания (текст)', max_length=255, blank=True)
    company_url = models.URLField('Ссылка на компанию', max_length=500, blank=True)
    location = models.CharField('Локация', max_length=255, blank=True)
    url = models.URLField('Ссылка', max_length=500)
    posted_date = models.DateField('Дата публикации', null=True, blank=True)
    benefits = models.CharField('Плашка', max_length=255, blank=True)

    # данные из details
    description = models.TextField('Описание', blank=True)
    description_html = models.TextField('Описание (HTML)', blank=True)
    seniority_level = models.CharField('Уровень', max_length=255, blank=True)
    employment_type = models.CharField('Тип занятости', max_length=255, blank=True)
    industries = models.CharField('Индустрии', max_length=500, blank=True)
    salary = models.CharField('Зарплата', max_length=255, blank=True)
    applicants = models.CharField('Откликов', max_length=100, blank=True)
    posted_time_ago = models.CharField('Опубликовано', max_length=100, blank=True)
    is_closed = models.BooleanField('Закрыта', default=False)

    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    attempts = models.IntegerField('Попыток', default=0)
    error_message = models.TextField('Ошибка', blank=True)
    details_parsed_at = models.DateTimeField('Детали собраны', null=True, blank=True)
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.company_name}'
