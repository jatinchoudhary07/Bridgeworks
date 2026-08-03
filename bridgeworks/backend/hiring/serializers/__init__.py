from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import (
    Job, Candidate, CandidateNote, HiringStage, JobPipelineStage,
    Application, ApplicationStageHistory,
    Interview, InterviewFeedback, Offer
)

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')


class JobSerializer(serializers.ModelSerializer):
    hiring_manager_detail = UserMinimalSerializer(source='hiring_manager', read_only=True)
    applications_count = serializers.SerializerMethodField()
    rejected_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        exclude = ('is_deleted',)
        read_only_fields = ('org_id', 'created_at', 'updated_at', 'published_at', 'closed_at')

    def get_applications_count(self, obj):
        return obj.applications.filter(is_deleted=False).count()

    def get_rejected_count(self, obj):
        return obj.applications.filter(is_deleted=False, current_stage__slug='rejected').count()


class JobListSerializer(serializers.ModelSerializer):
    applications_count = serializers.SerializerMethodField()
    shortlisted_count = serializers.SerializerMethodField()
    rejected_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = (
            'id', 'title', 'department', 'employment_type', 'location', 'location_type',
            'status', 'posting_type', 'openings_count', 'applications_count', 'shortlisted_count', 'rejected_count',
            'salary_min', 'salary_max', 'currency', 'experience_min', 'experience_max',
            'skills_required', 'google_form_url', 'created_at', 'published_at',
        )

    def get_applications_count(self, obj):
        return obj.applications.filter(is_deleted=False).count()

    def get_shortlisted_count(self, obj):
        return obj.applications.filter(is_deleted=False, current_stage__isnull=False).count()

    def get_rejected_count(self, obj):
        return obj.applications.filter(is_deleted=False, current_stage__slug='rejected').count()


class HiringStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HiringStage
        exclude = ('created_at',)
        read_only_fields = ('org_id',)


class JobPipelineStageSerializer(serializers.ModelSerializer):
    applications_count = serializers.SerializerMethodField()

    class Meta:
        model = JobPipelineStage
        fields = ('id', 'job', 'name', 'color', 'order', 'created_at', 'applications_count')
        read_only_fields = ('job', 'created_at')

    def get_applications_count(self, obj):
        return obj.applications.count()


class CandidateNoteSerializer(serializers.ModelSerializer):
    author_detail = UserMinimalSerializer(source='author', read_only=True)

    class Meta:
        model = CandidateNote
        fields = '__all__'
        read_only_fields = ('candidate', 'author', 'created_at', 'updated_at')


class CandidateSerializer(serializers.ModelSerializer):
    applications_count = serializers.SerializerMethodField()
    candidate_notes = CandidateNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Candidate
        exclude = ('is_deleted',)
        read_only_fields = ('org_id', 'created_at', 'updated_at')

    def get_applications_count(self, obj):
        return obj.applications.filter(is_deleted=False).count()


class CandidateListSerializer(serializers.ModelSerializer):
    applications_count = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = (
            'id', 'name', 'email', 'phone', 'skills', 'tags',
            'total_experience_years', 'current_company', 'current_designation',
            'source', 'applications_count', 'created_at',
        )

    def get_applications_count(self, obj):
        return obj.applications.filter(is_deleted=False).count()


class ApplicationStageHistorySerializer(serializers.ModelSerializer):
    from_stage_detail = HiringStageSerializer(source='from_stage', read_only=True)
    to_stage_detail = HiringStageSerializer(source='to_stage', read_only=True)
    moved_by_detail = UserMinimalSerializer(source='moved_by', read_only=True)

    class Meta:
        model = ApplicationStageHistory
        fields = '__all__'
        read_only_fields = ('application', 'moved_by', 'moved_at')


class ApplicationSerializer(serializers.ModelSerializer):
    candidate_detail = CandidateListSerializer(source='candidate', read_only=True)
    job_detail = JobListSerializer(source='job', read_only=True)
    current_stage_detail = HiringStageSerializer(source='current_stage', read_only=True)
    stage_history = ApplicationStageHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Application
        exclude = ('is_deleted',)
        read_only_fields = ('applied_at', 'updated_at')


class ApplicationListSerializer(serializers.ModelSerializer):
    candidate_detail = CandidateListSerializer(source='candidate', read_only=True)
    current_stage_detail = HiringStageSerializer(source='current_stage', read_only=True)
    pipeline_stage_detail = JobPipelineStageSerializer(source='pipeline_stage', read_only=True)

    class Meta:
        model = Application
        fields = (
            'id', 'candidate', 'candidate_detail', 'job',
            'current_stage', 'current_stage_detail',
            'pipeline_stage', 'pipeline_stage_detail',
            'applied_at', 'updated_at', 'extra_data', 'is_saved',
        )


class InterviewFeedbackSerializer(serializers.ModelSerializer):
    interviewer_detail = UserMinimalSerializer(source='interviewer', read_only=True)

    class Meta:
        model = InterviewFeedback
        fields = '__all__'
        read_only_fields = ('interview', 'interviewer', 'submitted_at', 'updated_at')


class InterviewSerializer(serializers.ModelSerializer):
    interviewers_detail = UserMinimalSerializer(source='interviewers', many=True, read_only=True)
    feedbacks = InterviewFeedbackSerializer(many=True, read_only=True)
    created_by_detail = UserMinimalSerializer(source='created_by', read_only=True)
    candidate_name = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_candidate_name(self, obj):
        return obj.application.candidate.name

    def get_job_title(self, obj):
        return obj.application.job.title


class OfferSerializer(serializers.ModelSerializer):
    candidate_name = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    created_by_detail = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = Offer
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_candidate_name(self, obj):
        return obj.application.candidate.name

    def get_job_title(self, obj):
        return obj.application.job.title
