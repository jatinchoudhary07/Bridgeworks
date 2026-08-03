import React from 'react';
import NotesSection from './sections/NotesSection';
import TasksSection from './sections/TasksSection';
import AnalyticsSection from './sections/AnalyticsSection';
import ProfileSection from './sections/ProfileSection';
import PersonalTodoSection from './sections/PersonalTodoSection';
import ExpensesSection from './sections/ExpensesSection';
import MyAttendanceSection from './sections/MyAttendanceSection';
import MyPayrollSection from './sections/MyPayrollSection';
import LeaveSection from './sections/LeaveSection';
import GallerySection from './sections/GallerySection';
import MeetingsSection from './sections/MeetingsSection';
import DiarySection from './sections/DiarySection';
import MyChatsSection from './sections/MyChatsSection';
import TrainingHubSection from './sections/TrainingHubSection';
import EmailSection from './sections/EmailSection';
import PlaceholderSection from './sections/PlaceholderSection';
import PersonalActivityLogs from '../activityLogs/PersonalActivityLogs';

const sectionTitle = {
    'my-notes': 'My Notes',
    'my-tasks': 'My Tasks',
    'my-chats': 'My Chats',
    'my-analytics': 'My Analytics',
    'my-profile': 'My Profile',
    expenses: 'Expenses',
    'my-attendance': 'My Attendance',
    'my-payroll': 'My Payroll',
    'leave-requests': 'Leave Requests',
    gallery: 'My Vault',
    logs: 'Logs',
    logbook: 'My Diary',
    'my-meetings': 'My Meetings',
};

export default function FeatureSections({ sectionId, members }) {
    if (sectionId === 'my-notes') return <NotesSection members={members} />;
    if (sectionId === 'my-tasks') return <TasksSection members={members} />;
    if (sectionId === 'my-chats') return <MyChatsSection />;
    if (sectionId === 'my-analytics') return <AnalyticsSection />;
    if (sectionId === 'my-profile') return <ProfileSection />;
    if (sectionId === 'personal-todo') return <PersonalTodoSection />;
    if (sectionId === 'expenses') return <ExpensesSection />;
    if (sectionId === 'my-attendance') return <MyAttendanceSection />;
    if (sectionId === 'my-payroll') return <MyPayrollSection />;
    if (sectionId === 'leave-requests') return <LeaveSection members={members} />;
    if (sectionId === 'gallery') return <GallerySection members={members} />;
    if (sectionId === 'logs') return <PersonalActivityLogs />;
    if (sectionId === 'logbook') return <DiarySection />;
    if (sectionId === 'my-meetings') return <MeetingsSection members={members} />;
    if (sectionId === 'training-hub') return <TrainingHubSection members={members} isAdminMode={false} />;
    if (sectionId === 'my-email')     return <EmailSection />;

    return <PlaceholderSection title={sectionTitle[sectionId] || 'Section'} />;
}
