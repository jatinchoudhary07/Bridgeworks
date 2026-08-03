from django.db import models
from django.contrib.auth import get_user_model
from .application import Application

User = get_user_model()


class Interview(models.Model):
    MODE_CHOICES = [
        ('google_meet', 'Google Meet'),
        ('zoom', 'Zoom'),
        ('phone', 'Phone'),
        ('in_person', 'In-Person'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
        ('no_show', 'No Show'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews')
    title = models.CharField(max_length=255, default='Interview')
    interviewers = models.ManyToManyField(User, related_name='assigned_interviews', blank=True)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='google_meet')
    meeting_link = models.URLField(max_length=1000, blank=True, default='')
    location = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    reminder_sent = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_interviews')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.title} — {self.application.candidate.name}"


class InterviewFeedback(models.Model):
    RECOMMENDATION_CHOICES = [
        ('strong_hire', 'Strong Hire'),
        ('hire', 'Hire'),
        ('neutral', 'Neutral'),
        ('reject', 'Reject'),
    ]

    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='feedbacks')
    interviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_feedbacks')
    overall_rating = models.PositiveSmallIntegerField(default=3)   # 1–5
    strengths = models.TextField(blank=True, default='')
    weaknesses = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default='neutral')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(fields=['interview', 'interviewer'], name='uniq_feedback_interview_interviewer')
        ]
