import React from 'react';
import { Box } from '@mui/material';
import TeamChat from '../../taskmanager/TeamChat';
import { useLocation } from 'react-router-dom';

export default function MyChatsSection() {
    const location = useLocation();
    const params = new URLSearchParams(location.search || '');
    const focusMessageId = (params.get('messageId') || '').trim();
    const focusWithUserId = (params.get('withUserId') || '').trim();
    const focusRoomId = (params.get('roomId') || '').trim();
    const focusChannelId = (params.get('channelId') || '').trim();
    const focusIsBroadcast = (params.get('isBroadcast') || '').trim();

    return (
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: '520px', width: '100%' }}>
            <TeamChat
                isOpen
                onClose={() => { }}
                embedded
                title="My Chats"
                showCloseButton={false}
                focusMessageId={focusMessageId}
                focusWithUserId={focusWithUserId}
                focusRoomId={focusRoomId}
                focusChannelId={focusChannelId}
                focusIsBroadcast={focusIsBroadcast}
            />
        </Box>
    );
}
