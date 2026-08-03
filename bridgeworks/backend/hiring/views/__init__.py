"""
Hiring views — thin API layer. All logic delegated to services.
"""
import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Job, Candidate, CandidateNote, HiringStage, JobPipelineStage,
    Application, ApplicationStageHistory,
    Interview, InterviewFeedback, Offer,
)
from ..serializers import (
    JobSerializer, JobListSerializer,
    CandidateSerializer, CandidateListSerializer, CandidateNoteSerializer,
    HiringStageSerializer, JobPipelineStageSerializer,
    ApplicationSerializer, ApplicationListSerializer,
    ApplicationStageHistorySerializer,
    InterviewSerializer,
    InterviewFeedbackSerializer,
    OfferSerializer,
)
from ..services import (
    publish_job, close_job,
    get_or_create_candidate, create_application,
    move_candidate_stage, import_google_form_candidates, sync_google_form_csv,
    schedule_interview, reschedule_interview,
    submit_feedback,
    create_offer, update_offer_status,
    convert_candidate_to_employee,
    get_hiring_analytics, ensure_default_stages,
)

logger = logging.getLogger(__name__)


def _get_org_id(request):
    try:
        return request.user.team_settings.organization.organization_id
    except Exception:
        return None


# ============================================================
# Job Views
# ============================================================

class JobListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = Job.objects.filter(org_id=org_id, is_deleted=False)

        status_filter = request.query_params.get('status')
        department_filter = request.query_params.get('department')
        search = request.query_params.get('search', '').strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if department_filter:
            qs = qs.filter(department=department_filter)
        if search:
            qs = qs.filter(title__icontains=search)

        serializer = JobListSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        org_id = _get_org_id(request)
        serializer = JobSerializer(data=request.data)
        if serializer.is_valid():
            job = serializer.save(org_id=org_id, created_by=request.user)
            ensure_default_stages(org_id)
            return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_job(self, job_id, org_id):
        return get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)

    def get(self, request, job_id):
        job = self._get_job(job_id, _get_org_id(request))
        return Response(JobSerializer(job).data)

    def patch(self, request, job_id):
        job = self._get_job(job_id, _get_org_id(request))
        serializer = JobSerializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, job_id):
        job = self._get_job(job_id, _get_org_id(request))
        job.is_deleted = True
        job.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id, org_id=_get_org_id(request), is_deleted=False)
        publish_job(job, request.user)
        return Response(JobSerializer(job).data)


class JobCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id, org_id=_get_org_id(request), is_deleted=False)
        close_job(job, request.user)
        return Response(JobSerializer(job).data)


# ============================================================
# Pipeline Stage Views
# ============================================================

class HiringStageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        ensure_default_stages(org_id)
        stages = HiringStage.objects.filter(org_id=org_id)
        return Response(HiringStageSerializer(stages, many=True).data)

    def post(self, request):
        org_id = _get_org_id(request)
        serializer = HiringStageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(org_id=org_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HiringStageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, stage_id):
        stage = get_object_or_404(HiringStage, pk=stage_id, org_id=_get_org_id(request))
        serializer = HiringStageSerializer(stage, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, stage_id):
        stage = get_object_or_404(HiringStage, pk=stage_id, org_id=_get_org_id(request))
        stage.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# Candidate Views
# ============================================================

class CandidateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = Candidate.objects.filter(org_id=org_id, is_deleted=False)

        search = request.query_params.get('search', '').strip()
        skills_filter = request.query_params.get('skills', '').strip()
        source_filter = request.query_params.get('source', '').strip()

        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(email__icontains=search) | qs.filter(current_company__icontains=search)
        if skills_filter:
            qs = qs.filter(skills__contains=[skills_filter])
        if source_filter:
            qs = qs.filter(source=source_filter)

        serializer = CandidateListSerializer(qs.distinct(), many=True)
        return Response(serializer.data)

    def post(self, request):
        org_id = _get_org_id(request)
        try:
            candidate, created = get_or_create_candidate(org_id, request.data, created_by=request.user)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CandidateSerializer(candidate).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class CandidateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_candidate(self, candidate_id, org_id):
        return get_object_or_404(Candidate, pk=candidate_id, org_id=org_id, is_deleted=False)

    def get(self, request, candidate_id):
        candidate = self._get_candidate(candidate_id, _get_org_id(request))
        return Response(CandidateSerializer(candidate).data)

    def patch(self, request, candidate_id):
        candidate = self._get_candidate(candidate_id, _get_org_id(request))
        serializer = CandidateSerializer(candidate, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, candidate_id):
        candidate = self._get_candidate(candidate_id, _get_org_id(request))
        candidate.is_deleted = True
        candidate.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, candidate_id):
        org_id = _get_org_id(request)
        candidate = get_object_or_404(Candidate, pk=candidate_id, org_id=org_id)
        notes = candidate.candidate_notes.all()
        return Response(CandidateNoteSerializer(notes, many=True).data)

    def post(self, request, candidate_id):
        org_id = _get_org_id(request)
        candidate = get_object_or_404(Candidate, pk=candidate_id, org_id=org_id)
        serializer = CandidateNoteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(candidate=candidate, author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# Application Views
# ============================================================

class ApplicationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = Application.objects.filter(job__org_id=org_id, is_deleted=False).select_related(
            'candidate', 'job', 'current_stage'
        )
        job_id = request.query_params.get('job_id')
        stage_slug = request.query_params.get('stage')
        if job_id:
            qs = qs.filter(job_id=job_id)
            
            # Heal/align stages for applications under this job
            # 1. If an application is Rejected but its pipeline_stage is not 'Rejected'
            rejected_apps = qs.filter(current_stage__slug='rejected')
            if rejected_apps.exists():
                rej_col = JobPipelineStage.objects.filter(job_id=job_id, name__iexact='rejected').first()
                if not rej_col:
                    job = Job.objects.filter(pk=job_id).first()
                    if job:
                        max_order = JobPipelineStage.objects.filter(job=job).count()
                        rej_col = JobPipelineStage.objects.create(
                            job=job,
                            name='Rejected',
                            color='#ef4444',
                            order=max_order
                        )
                if rej_col:
                    for app in rejected_apps:
                        if app.pipeline_stage_id != rej_col.id:
                            app.pipeline_stage = rej_col
                            app.save(update_fields=['pipeline_stage', 'updated_at'])
                            
            # 2. If an application is in the 'Rejected' pipeline column, but its current_stage is not 'rejected'
            rej_col = JobPipelineStage.objects.filter(job_id=job_id, name__iexact='rejected').first()
            if rej_col:
                mismatched_non_rej = qs.filter(pipeline_stage=rej_col).exclude(current_stage__slug='rejected')
                if mismatched_non_rej.exists():
                    rej_stage = HiringStage.objects.filter(org_id=org_id, slug='rejected').first()
                    if rej_stage:
                        for app in mismatched_non_rej:
                            move_candidate_stage(app, rej_stage, moved_by=request.user)
                            
        if stage_slug:
            qs = qs.filter(current_stage__slug=stage_slug)
        return Response(ApplicationListSerializer(qs, many=True).data)

    def post(self, request):
        org_id = _get_org_id(request)
        candidate_id = request.data.get('candidate_id')
        job_id = request.data.get('job_id')
        candidate = get_object_or_404(Candidate, pk=candidate_id, org_id=org_id)
        job = get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        try:
            application = create_application(candidate, job, created_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)


class ApplicationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        return Response(ApplicationSerializer(application).data)


class ApplicationMoveStageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        to_stage_id = request.data.get('stage_id')
        notes = request.data.get('notes', '')
        to_stage = get_object_or_404(HiringStage, pk=to_stage_id, org_id=org_id)
        application = move_candidate_stage(application, to_stage, moved_by=request.user, notes=notes)
        
        # Sync pipeline_stage to match the new HiringStage
        pipeline_stage = application.job.pipeline_stages.filter(name__iexact=to_stage.name).first()
        if not pipeline_stage:
            from django.utils.text import slugify
            slug = slugify(to_stage.name).replace('-', '_')
            pipeline_stage = application.job.pipeline_stages.filter(name__iexact=slug).first()
        if not pipeline_stage:
            pipeline_stage = application.job.pipeline_stages.filter(name__iexact=to_stage.slug).first()
        if pipeline_stage:
            application.pipeline_stage = pipeline_stage
            application.save(update_fields=['pipeline_stage'])
            
        return Response(ApplicationSerializer(application).data)


class ApplicationAcceptView(APIView):
    """Move application to the first pipeline stage (screening)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        
        # Ensure default stages exist for this organization
        ensure_default_stages(str(org_id))
        
        # First stage ordered by 'order', excluding rejected
        stage = HiringStage.objects.filter(org_id=org_id).exclude(slug='rejected').order_by('order').first()
        if not stage:
            stage = get_object_or_404(HiringStage, org_id=org_id, slug='screening')
            
        application = move_candidate_stage(application, stage, moved_by=request.user)
        
        # Ensure job pipeline stages are initialized
        if not application.job.pipeline_stages.exists():
            default_columns = [
                ('Screening', '#3b82f6', 0),
                ('Interview', '#f59e0b', 1),
                ('Offer', '#10b981', 2),
                ('Hired', '#22c55e', 3),
                ('Rejected', '#ef4444', 4),
            ]
            stages = [
                JobPipelineStage(job=application.job, name=name, color=color, order=order)
                for name, color, order in default_columns
            ]
            JobPipelineStage.objects.bulk_create(stages)
            
        # Assign pipeline_stage to 'Screening' column of the job if it exists
        screening_pipeline_stage = application.job.pipeline_stages.filter(name__iexact='screening').first()
        if not screening_pipeline_stage:
            max_order = application.job.pipeline_stages.count()
            screening_pipeline_stage = JobPipelineStage.objects.create(
                job=application.job,
                name='Screening',
                color='#3b82f6',
                order=max_order
            )
        if screening_pipeline_stage:
            application.pipeline_stage = screening_pipeline_stage
            application.save(update_fields=['pipeline_stage', 'updated_at'])
            
        return Response(ApplicationListSerializer(application).data)


class ApplicationRejectView(APIView):
    """Move application to the 'rejected' stage."""
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        stage = get_object_or_404(HiringStage, org_id=org_id, slug='rejected')
        application = move_candidate_stage(application, stage, moved_by=request.user)
        
        # Ensure job pipeline stages are initialized
        if not application.job.pipeline_stages.exists():
            default_columns = [
                ('Screening', '#3b82f6', 0),
                ('Interview', '#f59e0b', 1),
                ('Offer', '#10b981', 2),
                ('Hired', '#22c55e', 3),
                ('Rejected', '#ef4444', 4),
            ]
            stages = [
                JobPipelineStage(job=application.job, name=name, color=color, order=order)
                for name, color, order in default_columns
            ]
            JobPipelineStage.objects.bulk_create(stages)
            
        # Assign pipeline_stage to 'Rejected' column of the job if it exists
        rejected_pipeline_stage = application.job.pipeline_stages.filter(name__iexact='rejected').first()
        if not rejected_pipeline_stage:
            max_order = application.job.pipeline_stages.count()
            rejected_pipeline_stage = JobPipelineStage.objects.create(
                job=application.job,
                name='Rejected',
                color='#ef4444',
                order=max_order
            )
        if rejected_pipeline_stage:
            application.pipeline_stage = rejected_pipeline_stage
            application.save(update_fields=['pipeline_stage', 'updated_at'])
            
        return Response(ApplicationListSerializer(application).data)


class ApplicationSaveToggleView(APIView):
    """Toggle the is_saved bookmark on an application."""
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        application.is_saved = not application.is_saved
        application.save(update_fields=['is_saved'])
        return Response({'id': application.id, 'is_saved': application.is_saved})


class ApplicationPipelineStageView(APIView):
    """Move an application to a job pipeline stage (column)."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        stage_id = request.data.get('pipeline_stage_id')
        if stage_id:
            stage = get_object_or_404(JobPipelineStage, pk=stage_id, job__org_id=org_id)
            application.pipeline_stage = stage
            
            # Find matching HiringStage
            hiring_stage = HiringStage.objects.filter(org_id=org_id, name__iexact=stage.name).first()
            if not hiring_stage:
                from django.utils.text import slugify
                slug = slugify(stage.name).replace('-', '_')
                hiring_stage = HiringStage.objects.filter(org_id=org_id, slug=slug).first()
            if not hiring_stage:
                hiring_stage = HiringStage.objects.filter(org_id=org_id, name__icontains=stage.name).first()
            if not hiring_stage:
                for hs in HiringStage.objects.filter(org_id=org_id):
                    if hs.name.lower() in stage.name.lower() or hs.slug.replace('_', ' ') in stage.name.lower():
                        hiring_stage = hs
                        break
            
            if hiring_stage:
                move_candidate_stage(application, hiring_stage, moved_by=request.user)
                
            application.pipeline_stage = stage
            application.save(update_fields=['pipeline_stage'])
        else:
            application.pipeline_stage = None
            application.save(update_fields=['pipeline_stage'])
            
        return Response(ApplicationListSerializer(application).data)


class JobPipelineStageListView(APIView):
    """List and create pipeline stages for a specific job."""
    permission_classes = [IsAuthenticated]

    DEFAULT_COLUMNS = [
        ('Screening', '#3b82f6', 0),
        ('Interview', '#f59e0b', 1),
        ('Offer', '#10b981', 2),
        ('Hired', '#22c55e', 3),
        ('Rejected', '#ef4444', 4),
    ]

    def get(self, request, job_id):
        org_id = _get_org_id(request)
        job = get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        stages = JobPipelineStage.objects.filter(job=job)
        return Response(JobPipelineStageSerializer(stages, many=True).data)

    def post(self, request, job_id):
        org_id = _get_org_id(request)
        job = get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        # Special action: init with defaults
        if request.data.get('action') == 'init':
            existing = JobPipelineStage.objects.filter(job=job)
            if existing.exists():
                return Response({'error': 'Pipeline already initialized.'}, status=400)
            stages = [
                JobPipelineStage(job=job, name=name, color=color, order=order)
                for name, color, order in self.DEFAULT_COLUMNS
            ]
            JobPipelineStage.objects.bulk_create(stages)
            created = JobPipelineStage.objects.filter(job=job)
            return Response(JobPipelineStageSerializer(created, many=True).data, status=201)
        # Special action: reorder stages
        if request.data.get('action') == 'reorder':
            orders = request.data.get('orders', [])
            for item in orders:
                stage_id = item.get('id')
                stage_order = item.get('order')
                if stage_id is not None and stage_order is not None:
                    JobPipelineStage.objects.filter(job=job, pk=stage_id).update(order=stage_order)
            stages = JobPipelineStage.objects.filter(job=job)
            return Response(JobPipelineStageSerializer(stages, many=True).data)
        # Normal create
        name = request.data.get('name', '').strip()
        color = request.data.get('color', '#6366f1')
        if not name:
            return Response({'error': 'name is required'}, status=400)
        if JobPipelineStage.objects.filter(job=job, name=name).exists():
            return Response({'error': f'A column named "{name}" already exists.'}, status=400)
        max_order = JobPipelineStage.objects.filter(job=job).count()
        stage = JobPipelineStage.objects.create(job=job, name=name, color=color, order=max_order)
        return Response(JobPipelineStageSerializer(stage).data, status=201)


class JobPipelineStageDetailView(APIView):
    """Update or delete a single job pipeline stage."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, job_id, stage_id):
        org_id = _get_org_id(request)
        get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        stage = get_object_or_404(JobPipelineStage, pk=stage_id, job_id=job_id)
        serializer = JobPipelineStageSerializer(stage, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, job_id, stage_id):
        org_id = _get_org_id(request)
        get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        stage = get_object_or_404(JobPipelineStage, pk=stage_id, job_id=job_id)
        # Prevent deletion if there are applications in this stage
        if stage.applications.exists():
            return Response({'error': 'Cannot delete column because it has candidates.'}, status=400)
        stage.delete()
        return Response(status=204)


class GoogleFormImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        job_id = request.data.get('job_id')
        spreadsheet_id = request.data.get('spreadsheet_id')
        credentials_json = request.data.get('credentials_json', {})
        if not job_id or not spreadsheet_id:
            return Response({'error': 'job_id and spreadsheet_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = import_google_form_candidates(
                org_id, job_id, spreadsheet_id, credentials_json, created_by=request.user
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class JobGoogleFormSyncView(APIView):
    """Sync candidates from the Google Sheet CSV URL stored on the job."""
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        org_id = _get_org_id(request)
        get_object_or_404(Job, pk=job_id, org_id=org_id, is_deleted=False)
        try:
            result = sync_google_form_csv(org_id, job_id, created_by=request.user)
        except ValueError as e:
            err = str(e)
            if err == 'FORM_URL':
                return Response({'error': 'FORM_URL', 'is_form_url': True}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Google Form CSV sync error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)


# ============================================================
# Interview Views
# ============================================================

class InterviewListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = Interview.objects.filter(
            application__job__org_id=org_id
        ).select_related('application__candidate', 'application__job').prefetch_related('interviewers', 'feedbacks')

        status_filter = request.query_params.get('status')
        application_id = request.query_params.get('application_id')

        # Interviewers only see their own interviews
        if not _is_hr_or_owner(request):
            qs = qs.filter(interviewers=request.user)

        if status_filter:
            qs = qs.filter(status=status_filter)
        if application_id:
            qs = qs.filter(application_id=application_id)

        return Response(InterviewSerializer(qs, many=True).data)

    def post(self, request):
        org_id = _get_org_id(request)
        application_id = request.data.get('application_id')
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        try:
            interview = schedule_interview(application, request.data, created_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InterviewSerializer(interview).data, status=status.HTTP_201_CREATED)


class InterviewDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_interview(self, interview_id, org_id):
        return get_object_or_404(Interview, pk=interview_id, application__job__org_id=org_id)

    def get(self, request, interview_id):
        interview = self._get_interview(interview_id, _get_org_id(request))
        return Response(InterviewSerializer(interview).data)

    def patch(self, request, interview_id):
        org_id = _get_org_id(request)
        interview = self._get_interview(interview_id, org_id)
        serializer = InterviewSerializer(interview, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InterviewRescheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, interview_id):
        org_id = _get_org_id(request)
        interview = get_object_or_404(Interview, pk=interview_id, application__job__org_id=org_id)
        scheduled_at = request.data.get('scheduled_at')
        if not scheduled_at:
            return Response({'error': 'scheduled_at is required.'}, status=status.HTTP_400_BAD_REQUEST)
        interview = reschedule_interview(interview, scheduled_at, notes=request.data.get('notes', ''))
        return Response(InterviewSerializer(interview).data)


# ============================================================
# Feedback Views
# ============================================================

class InterviewFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, interview_id):
        org_id = _get_org_id(request)
        interview = get_object_or_404(Interview, pk=interview_id, application__job__org_id=org_id)
        feedbacks = interview.feedbacks.all()
        return Response(InterviewFeedbackSerializer(feedbacks, many=True).data)

    def post(self, request, interview_id):
        org_id = _get_org_id(request)
        interview = get_object_or_404(Interview, pk=interview_id, application__job__org_id=org_id)
        feedback = submit_feedback(interview, request.user, request.data)
        return Response(InterviewFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


# ============================================================
# Offer Views
# ============================================================

class OfferListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = Offer.objects.filter(
            application__job__org_id=org_id
        ).select_related('application__candidate', 'application__job')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(OfferSerializer(qs, many=True).data)


class OfferCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        application_id = request.data.get('application_id')
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        try:
            offer = create_offer(application, request.data, created_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)


class OfferDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_offer(self, offer_id, org_id):
        return get_object_or_404(Offer, pk=offer_id, application__job__org_id=org_id)

    def get(self, request, offer_id):
        offer = self._get_offer(offer_id, _get_org_id(request))
        return Response(OfferSerializer(offer).data)

    def patch(self, request, offer_id):
        offer = self._get_offer(offer_id, _get_org_id(request))
        new_status = request.data.get('status')
        if new_status:
            offer = update_offer_status(offer, new_status)
        serializer = OfferSerializer(offer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# Employee Conversion
# ============================================================

class ConvertToEmployeeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        org_id = _get_org_id(request)
        application = get_object_or_404(Application, pk=application_id, job__org_id=org_id, is_deleted=False)
        try:
            result = convert_candidate_to_employee(application, converted_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'member_id': result['member'].pk,
            'created': result['created'],
            'message': 'Candidate converted to employee successfully.' if result['created'] else 'Employee record already exists.',
        })


# ============================================================
# Analytics
# ============================================================

class HiringAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        data = get_hiring_analytics(org_id)
        return Response(data)


# ============================================================
# Helpers
# ============================================================

def _is_hr_or_owner(request):
    from core.permissions import is_org_owner
    if is_org_owner(request.user):
        return True
    try:
        role = request.user.team_settings.role
        if role:
            perms = role.permissions if hasattr(role, 'permissions') else {}
            return bool(perms.get('human_resources', {}).get('hiring'))
    except Exception:
        pass
    return False
