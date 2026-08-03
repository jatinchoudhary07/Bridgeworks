from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from core.models import PersonalTodoItem


User = get_user_model()


class PersonalTodoVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(username='creator', password='pass1234')
        self.assignee = User.objects.create_user(username='assignee', password='pass1234')
        self.outsider = User.objects.create_user(username='outsider', password='pass1234')

    def test_list_includes_task_when_user_is_in_assignee_ids_as_int(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task assigned by list int',
            meta={
                'type': 'task',
                'assignee_id': self.creator.id,
                'assignee_ids': [self.creator.id, self.assignee.id],
            },
        )

        self.client.force_authenticate(user=self.assignee)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.get('/api/mydesk/todos/')

        self.assertEqual(response.status_code, 200)
        ids = {entry['id'] for entry in response.json()}
        self.assertIn(task.id, ids)

    def test_list_includes_task_when_user_is_in_assignee_ids_as_string(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task assigned by list str',
            meta={
                'type': 'task',
                'assignee_id': str(self.creator.id),
                'assignee_ids': [str(self.creator.id), str(self.assignee.id)],
            },
        )

        self.client.force_authenticate(user=self.assignee)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.get('/api/mydesk/todos/')

        self.assertEqual(response.status_code, 200)
        ids = {entry['id'] for entry in response.json()}
        self.assertIn(task.id, ids)

    def test_list_excludes_task_when_user_not_in_any_assignment_field(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task not assigned to outsider',
            meta={
                'type': 'task',
                'assignee_id': self.assignee.id,
                'assignee_ids': [self.assignee.id],
            },
        )

        self.client.force_authenticate(user=self.outsider)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.get('/api/mydesk/todos/')

        self.assertEqual(response.status_code, 200)
        ids = {entry['id'] for entry in response.json()}
        self.assertNotIn(task.id, ids)

    def test_delete_allows_assigner(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task created by assigner',
            meta={
                'type': 'task',
                'assigned_by_id': self.creator.id,
                'assignee_id': self.assignee.id,
                'assignee_ids': [self.assignee.id],
            },
        )

        self.client.force_authenticate(user=self.creator)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.delete(f'/api/mydesk/todos/{task.id}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(PersonalTodoItem.objects.filter(id=task.id).exists())

    def test_delete_forbidden_for_assignee_who_is_not_assigner(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task assigned to someone else',
            meta={
                'type': 'task',
                'assigned_by_id': self.creator.id,
                'assignee_id': self.assignee.id,
                'assignee_ids': [self.assignee.id],
            },
        )

        self.client.force_authenticate(user=self.assignee)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.delete(f'/api/mydesk/todos/{task.id}/')

        self.assertEqual(response.status_code, 403)
        self.assertTrue(PersonalTodoItem.objects.filter(id=task.id).exists())

    def test_list_type_task_returns_only_task_items(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task item',
            meta={'type': 'task', 'assignee_id': self.creator.id},
        )
        personal = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Personal checklist',
            meta={'type': 'personal'},
        )

        self.client.force_authenticate(user=self.creator)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.get('/api/mydesk/todos/?type=task')

        self.assertEqual(response.status_code, 200)
        ids = {entry['id'] for entry in response.json()}
        self.assertIn(task.id, ids)
        self.assertNotIn(personal.id, ids)

    def test_list_type_personal_returns_personal_and_legacy_items(self):
        task = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Task item',
            meta={'type': 'task', 'assignee_id': self.creator.id},
        )
        personal = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Personal checklist',
            meta={'type': 'personal'},
        )
        legacy_personal = PersonalTodoItem.objects.create(
            user=self.creator,
            org_id='',
            text='Legacy personal checklist',
            meta={},
        )

        self.client.force_authenticate(user=self.creator)
        with patch('core.views_mydesk._get_org_id_or_none', return_value=''):
            response = self.client.get('/api/mydesk/todos/?type=personal')

        self.assertEqual(response.status_code, 200)
        ids = {entry['id'] for entry in response.json()}
        self.assertIn(personal.id, ids)
        self.assertIn(legacy_personal.id, ids)
        self.assertNotIn(task.id, ids)
