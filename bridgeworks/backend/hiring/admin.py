from django.contrib import admin
from .models import (
    Job, Candidate, CandidateNote, HiringStage,
    Application, ApplicationStageHistory,
    Interview, InterviewFeedback, Offer
)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'status', 'employment_type', 'openings_count', 'org_id', 'created_at')
    list_filter = ('status', 'employment_type', 'department')
    search_fields = ('title', 'org_id')


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'source', 'org_id', 'created_at')
    search_fields = ('name', 'email', 'org_id')
    list_filter = ('source',)


@admin.register(HiringStage)
class HiringStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'org_id', 'is_terminal')
    list_filter = ('org_id',)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'job', 'current_stage', 'applied_at')
    list_filter = ('current_stage',)
    search_fields = ('candidate__name', 'candidate__email', 'job__title')


@admin.register(ApplicationStageHistory)
class ApplicationStageHistoryAdmin(admin.ModelAdmin):
    list_display = ('application', 'from_stage', 'to_stage', 'moved_by', 'moved_at')


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'scheduled_at', 'mode', 'status')
    list_filter = ('status', 'mode')


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ('interview', 'interviewer', 'overall_rating', 'recommendation', 'submitted_at')


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('application', 'offered_salary', 'status', 'joining_date', 'created_at')
    list_filter = ('status',)
