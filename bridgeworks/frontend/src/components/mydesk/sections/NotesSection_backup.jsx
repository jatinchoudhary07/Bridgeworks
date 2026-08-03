import React from 'react';
import MyNotes from './MyNotes';

/**
 * NotesSection - Wrapper component for the new MyNotes redesign
 * This component maintains backward compatibility with the existing routing
 */
export default function NotesSection({ members = [] }) {
  return <MyNotes />;
}
