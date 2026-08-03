from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import PersonalTodoItem, UnifiedNotification


User = get_user_model()


class TaskAssignmentNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.assigner = User.objects.create_user(username='assigner', password='pass1234', first_name='Assigner')
        self.assignee_one = User.objects.create_user(username='assignee_one', password='pass1234')
        self.assignee_two = User.objects.create_user(username='assignee_two', password='pass1234')

    def test_create_task_notifies_assignees(self):
        self.client.force_authenticate(user=self.assigner)
        payload = {
            'text': 'Prepare report',
            'is_done': False,
            'recurring': 'none',
            'sort_order': 0,
            'meta': {
                'type': 'task',
                'title': 'Prepare report',
                'priority': 'critical',
                'assignee_id': self.assignee_one.id,
                'assignee_ids': [self.assignee_one.id, self.assignee_two.id],
                'assigned_by_id': self.assigner.id,
                'assignedBy': self.assigner.username,
            },
        }

        with patch('core.views_mydesk._get_org_id_or_none', return_value=''), patch('core.services.notifications.get_channel_layer', return_value=None):
            response = self.client.post('/api/mydesk/todos/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        todo_id = str(response.json()['id'])

        notifications = list(
            UnifiedNotification.objects.filter(
                module='tasks',
                action='share',
                title='Task assigned to you',
                entity_type='personal_todo',
                entity_id=todo_id,
            )
        )
        notified_user_ids = {notification.recipient_id for notification in notifications}

        self.assertEqual(notified_user_ids, {self.assignee_one.id, self.assignee_two.id})
        for notification in notifications:
            self.assertEqual(notification.metadata.get('task_priority'), 'critical')
            self.assertEqual(notification.metadata.get('sound_category'), 'task_urgent')
        self.assertFalse(UnifiedNotification.objects.filter(recipient=self.assigner, entity_id=todo_id).exists())

    def test_create_task_assigned_to_self_does_not_notify_self(self):
        self.client.force_authenticate(user=self.assigner)
        payload = {
            'text': 'Personal task',
            'is_done': False,
            'recurring': 'none',
            'sort_order': 0,
            'meta': {
                'type': 'task',
                'title': 'Personal task',
                'assignee_id': self.assigner.id,
                'assignee_ids': [self.assigner.id],
                'assigned_by_id': self.assigner.id,
                'assignedBy': self.assigner.username,
            },
        }

        with patch('core.views_mydesk._get_org_id_or_none', return_value=''), patch('core.services.notifications.get_channel_layer', return_value=None):
            response = self.client.post('/api/mydesk/todos/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        todo_id = str(response.json()['id'])
        self.assertFalse(
            UnifiedNotification.objects.filter(
                module='tasks',
                action='share',
                title='Task assigned to you',
                entity_type='personal_todo',
                entity_id=todo_id,
            ).exists()
        )

    def test_patch_task_notifies_only_new_assignee(self):
        task = PersonalTodoItem.objects.create(
            user=self.assigner,
            org_id='',
            text='Follow up order',
            meta={
                'type': 'task',
                'title': 'Follow up order',
                'priority': 'low',
                'assignee_id': self.assignee_one.id,
                'assignee_ids': [self.assignee_one.id],
                'assigned_by_id': self.assigner.id,
                'assignedBy': self.assigner.username,
            },
        )

        self.client.force_authenticate(user=self.assigner)
        payload = {
            'meta': {
                'type': 'task',
                'title': 'Follow up order',
                'priority': 'low',
                'assignee_id': self.assignee_one.id,
                'assignee_ids': [self.assignee_one.id, self.assignee_two.id],
                'assigned_by_id': self.assigner.id,
                'assignedBy': self.assigner.username,
            },
        }

        with patch('core.views_mydesk._get_org_id_or_none', return_value=''), patch('core.services.notifications.get_channel_layer', return_value=None):
            response = self.client.patch(f'/api/mydesk/todos/{task.id}/', payload, format='json')

        self.assertEqual(response.status_code, 200)

        notifications = UnifiedNotification.objects.filter(
            module='tasks',
            action='share',
            title='Task assigned to you',
            entity_type='personal_todo',
            entity_id=str(task.id),
        )

        self.assertEqual(notifications.count(), 1)
        created = notifications.first()
        self.assertEqual(created.recipient_id, self.assignee_two.id)
        self.assertEqual(created.metadata.get('task_priority'), 'low')
        self.assertEqual(created.metadata.get('sound_category'), 'task_normal')
