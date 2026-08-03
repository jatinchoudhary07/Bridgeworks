import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Autocomplete,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    MenuItem,
    Stack,
    TextField,
} from '@mui/material';

const ACTION_LABELS = {
    meeting: 'Meeting',
    task: 'Task',
};

const toInputDate = (dateKey) => {
    if (!dateKey || !/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) {
        return new Date().toISOString().slice(0, 10);
    }
    return dateKey;
};

export default function ScheduleModal({
    open,
    actionType,
    selectedDate,
    members,
    submitting,
    connected,
    error,
    onClose,
    onSubmit,
    onConnectGoogle,
}) {
    const [title, setTitle] = useState('');
    const [date, setDate] = useState(toInputDate(selectedDate));
    const [time, setTime] = useState('10:00');
    const [notes, setNotes] = useState('');
    const [participants, setParticipants] = useState([]);
    const [platform, setPlatform] = useState('google_meet');

    useEffect(() => {
        if (!open) return;
        setTitle('');
        setDate(toInputDate(selectedDate));
        setTime('10:00');
        setNotes('');
        setParticipants([]);
        setPlatform('google_meet');
    }, [open, actionType, selectedDate]);

    const canSubmit = useMemo(() => {
        if (!title.trim()) return false;
        if (!date || !time) return false;
        if (!connected) return false;
        return true;
    }, [title, date, time, connected]);

    const handleSubmit = () => {
        const start = `${date}T${time}:00`;

        onSubmit({
            actionType,
            title: title.trim(),
            date,
            time,
            start,
            notes: notes.trim(),
            participants,
            platform,
        });
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>Schedule {ACTION_LABELS[actionType] || 'Item'}</DialogTitle>
            <DialogContent>
                {!connected && (
                    <Alert
                        severity="warning"
                        sx={{ mb: 2 }}
                        action={(
                            <Button color="inherit" size="small" onClick={onConnectGoogle}>
                                Connect
                            </Button>
                        )}
                    >
                        Google Calendar is not connected for this account.
                    </Alert>
                )}

                {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

                <Stack spacing={2} sx={{ mt: 1 }}>
                    <TextField
                        label="Title"
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                        fullWidth
                        required
                    />

                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                        <TextField
                            label="Date"
                            type="date"
                            value={date}
                            onChange={(event) => setDate(event.target.value)}
                            InputLabelProps={{ shrink: true }}
                            fullWidth
                        />
                        <TextField
                            label="Time"
                            type="time"
                            value={time}
                            onChange={(event) => setTime(event.target.value)}
                            InputLabelProps={{ shrink: true }}
                            fullWidth
                        />
                    </Stack>

                    {actionType === 'meeting' && (
                        <>
                            <Autocomplete
                                multiple
                                options={members}
                                value={participants}
                                onChange={(_, value) => setParticipants(value)}
                                getOptionLabel={(option) => option.full_name || option.username || option.email || 'Member'}
                                renderInput={(params) => <TextField {...params} label="Participants" placeholder="Select members" />}
                            />

                            <TextField
                                select
                                label="Platform"
                                value={platform}
                                onChange={(event) => setPlatform(event.target.value)}
                                fullWidth
                            >
                                <MenuItem value="google_meet">Google Meet</MenuItem>
                                <MenuItem value="in_person">In-person</MenuItem>
                            </TextField>
                        </>
                    )}

                    <TextField
                        label="Notes"
                        value={notes}
                        onChange={(event) => setNotes(event.target.value)}
                        fullWidth
                        multiline
                        minRows={3}
                    />
                </Stack>
            </DialogContent>

            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button onClick={onClose}>Cancel</Button>
                <Button disabled={!canSubmit || submitting} variant="contained" onClick={handleSubmit}>
                    {submitting ? 'Saving...' : 'Save'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}