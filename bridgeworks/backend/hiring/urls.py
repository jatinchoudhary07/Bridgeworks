from django.urls import path
from .views import (
    # Jobs
    JobListCreateView,
    JobDetailView,
    JobPublishView,
    JobCloseView,
    JobGoogleFormSyncView,
    # Stages
    HiringStageListView,
    HiringStageDetailView,
    # Candidates
    CandidateListCreateView,
    CandidateDetailView,
    CandidateNoteView,
    # Applications
    ApplicationListCreateView,
    ApplicationDetailView,
    ApplicationMoveStageView,
    ApplicationAcceptView,
    ApplicationRejectView,
    ApplicationSaveToggleView,
    ApplicationPipelineStageView,
    GoogleFormImportView,
    # Job Pipeline Stages
    JobPipelineStageListView,
    JobPipelineStageDetailView,
    # Interviews
    InterviewListCreateView,
    InterviewDetailView,
    InterviewRescheduleView,
    InterviewFeedbackView,
    # Offers
    OfferListView,
    OfferCreateView,
    OfferDetailView,
    # Conversion
    ConvertToEmployeeView,
    # Analytics
    HiringAnalyticsView,
)

app_name = 'hiring'

urlpatterns = [
    # ---- Jobs ----
    path('jobs/', JobListCreateView.as_view(), name='job-list'),
    path('jobs/<int:job_id>/', JobDetailView.as_view(), name='job-detail'),
    path('jobs/<int:job_id>/publish/', JobPublishView.as_view(), name='job-publish'),
    path('jobs/<int:job_id>/close/', JobCloseView.as_view(), name='job-close'),

    # ---- Pipeline Stages ----
    path('stages/', HiringStageListView.as_view(), name='stage-list'),
    path('stages/<int:stage_id>/', HiringStageDetailView.as_view(), name='stage-detail'),

    # ---- Candidates ----
    path('candidates/', CandidateListCreateView.as_view(), name='candidate-list'),
    path('candidates/<int:candidate_id>/', CandidateDetailView.as_view(), name='candidate-detail'),
    path('candidates/<int:candidate_id>/notes/', CandidateNoteView.as_view(), name='candidate-notes'),

    # ---- Applications ----
    path('applications/', ApplicationListCreateView.as_view(), name='application-list'),
    path('applications/<int:application_id>/', ApplicationDetailView.as_view(), name='application-detail'),
    path('applications/<int:application_id>/move-stage/', ApplicationMoveStageView.as_view(), name='application-move-stage'),
    path('applications/<int:application_id>/accept/', ApplicationAcceptView.as_view(), name='application-accept'),
    path('applications/<int:application_id>/reject/', ApplicationRejectView.as_view(), name='application-reject'),
    path('applications/<int:application_id>/save/', ApplicationSaveToggleView.as_view(), name='application-save'),
    path('applications/<int:application_id>/pipeline-stage/', ApplicationPipelineStageView.as_view(), name='application-pipeline-stage'),
    path('applications/<int:application_id>/convert-to-employee/', ConvertToEmployeeView.as_view(), name='convert-to-employee'),

    # ---- Job Pipeline Stages ----
    path('jobs/<int:job_id>/pipeline/', JobPipelineStageListView.as_view(), name='job-pipeline-list'),
    path('jobs/<int:job_id>/pipeline/<int:stage_id>/', JobPipelineStageDetailView.as_view(), name='job-pipeline-detail'),

    # ---- Google Form Import ----
    path('import/google-form/', GoogleFormImportView.as_view(), name='google-form-import'),
    path('jobs/<int:job_id>/sync-form/', JobGoogleFormSyncView.as_view(), name='job-sync-form'),

    # ---- Interviews ----
    path('interviews/', InterviewListCreateView.as_view(), name='interview-list'),
    path('interviews/<int:interview_id>/', InterviewDetailView.as_view(), name='interview-detail'),
    path('interviews/<int:interview_id>/reschedule/', InterviewRescheduleView.as_view(), name='interview-reschedule'),
    path('interviews/<int:interview_id>/feedback/', InterviewFeedbackView.as_view(), name='interview-feedback'),

    # ---- Offers ----
    path('offers/', OfferListView.as_view(), name='offer-list'),
    path('offers/create/', OfferCreateView.as_view(), name='offer-create'),
    path('offers/<int:offer_id>/', OfferDetailView.as_view(), name='offer-detail'),

    # ---- Analytics ----
    path('analytics/', HiringAnalyticsView.as_view(), name='analytics'),
]
