from django.contrib import admin
from django.utils.html import format_html

from .models import SearchQuery, Job, Company


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('keywords', 'country', 'is_active', 'jobs_found', 'last_run_at', 'created_at')
    list_filter = ('is_active', 'country')
    list_editable = ('is_active',)
    search_fields = ('keywords', 'country')
    readonly_fields = ('jobs_found', 'last_run_at', 'last_error', 'created_at')


@admin.action(description='Отправить на повторную обработку (details)')
def reset_status(modeladmin, request, queryset):
    count = queryset.update(status='new', attempts=0, error_message='')
    modeladmin.message_user(request, f'Сброшено вакансий: {count}')


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('job_id', 'title', 'company_name', 'location', 'seniority_level',
                    'employment_type', 'posted_date', 'status', 'attempts', 'open_link')
    list_filter = ('status', 'seniority_level', 'employment_type', 'is_closed', 'search_queries')
    search_fields = ('job_id', 'title', 'company_name', 'location')
    readonly_fields = ('created_at', 'updated_at', 'details_parsed_at')
    raw_id_fields = ('company',)
    filter_horizontal = ('search_queries',)
    exclude = ('description_html',)
    actions = [reset_status]
    list_per_page = 50

    @admin.display(description='Ссылка')
    def open_link(self, obj):
        return format_html('<a href="{}" target="_blank">открыть</a>', obj.url)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'company_size', 'headquarters', 'followers', 'status', 'jobs_count')
    list_filter = ('status', 'company_size', 'company_type')
    search_fields = ('name', 'slug', 'industry')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Вакансий')
    def jobs_count(self, obj):
        return obj.jobs.count()
