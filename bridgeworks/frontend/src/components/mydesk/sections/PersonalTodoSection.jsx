import React, { useEffect, useState } from 'react';
import {
    Button,
    Chip,
    FormControl,
    IconButton,
    InputLabel,
    List,
    ListItem,
    ListItemText,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import { ArrowDownward as ArrowDownwardIcon, ArrowUpward as ArrowUpwardIcon } from '@mui/icons-material';
import { createMyDeskTodo, listMyDeskTodos, updateMyDeskTodo } from '../mydeskService';

export default function PersonalTodoSection() {
    const [items, setItems] = useState([]);
    const [newText, setNewText] = useState('');
    const [recurring, setRecurring] = useState('daily');
    const [draggingId, setDraggingId] = useState(null);

    useEffect(() => {
        let mounted = true;
        listMyDeskTodos({ type: 'personal', includeAttachments: false })
            .then((data) => {
                if (!mounted) return;
                const allItems = Array.isArray(data) ? data : [];
                const personalItems = allItems.filter((entry) => {
                    const meta = entry?.meta;
                    if (!meta || typeof meta !== 'object') return true;
                    return meta.type !== 'task';
                });
                setItems(personalItems);
            })
            .catch(() => { });

        return () => {
            mounted = false;
        };
    }, []);

    const addItem = async () => {
        if (!newText.trim()) return;
        try {
            const created = await createMyDeskTodo({
                text: newText,
                recurring,
                is_done: false,
                sort_order: items.length,
                meta: { type: 'personal' },
            });
            setItems((previous) => [...previous, created]);
        } catch {
            return;
        }
        setNewText('');
    };

    const moveItem = async (fromId, toId) => {
        const copy = [...items];
        const fromIndex = copy.findIndex((item) => item.id === fromId);
        const toIndex = copy.findIndex((item) => item.id === toId);
        if (fromIndex < 0 || toIndex < 0) return;
        const [moved] = copy.splice(fromIndex, 1);
        copy.splice(toIndex, 0, moved);
        const withOrder = copy.map((item, index) => ({ ...item, sort_order: index }));
        setItems(withOrder);
        try {
            await Promise.all(withOrder.map((item) => updateMyDeskTodo(item.id, { sort_order: item.sort_order })));
        } catch {
        }
    };

    return (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                <Chip size="small" label="Private" color="secondary" />
                <Typography variant="caption" color="text.secondary">Visible only to you</Typography>
            </Stack>

            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                <TextField size="small" fullWidth label="New checklist item" value={newText} onChange={(event) => setNewText(event.target.value)} />
                <FormControl size="small" sx={{ minWidth: 140 }}>
                    <InputLabel>Recurring</InputLabel>
                    <Select label="Recurring" value={recurring} onChange={(event) => setRecurring(event.target.value)}>
                        <MenuItem value="daily">Daily</MenuItem>
                        <MenuItem value="weekly">Weekly</MenuItem>
                    </Select>
                </FormControl>
                <Button variant="contained" onClick={addItem}>Add</Button>
            </Stack>

            <List sx={{ mt: 1 }}>
                {items.map((item, index) => (
                    <ListItem
                        key={item.id}
                        divider
                        draggable
                        onDragStart={() => setDraggingId(item.id)}
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={() => {
                            if (draggingId) moveItem(draggingId, item.id);
                            setDraggingId(null);
                        }}
                        secondaryAction={(
                            <Stack direction="row" spacing={0.5}>
                                <IconButton size="small" onClick={() => index > 0 && moveItem(item.id, items[index - 1].id)}><ArrowUpwardIcon fontSize="small" /></IconButton>
                                <IconButton size="small" onClick={() => index < items.length - 1 && moveItem(item.id, items[index + 1].id)}><ArrowDownwardIcon fontSize="small" /></IconButton>
                            </Stack>
                        )}
                    >
                        <ListItemText
                            primary={item.text}
                            secondary={`Recurring: ${item.recurring}`}
                            primaryTypographyProps={{ sx: { textDecoration: item.is_done ? 'line-through' : 'none' } }}
                            onClick={async () => {
                                const nextDone = !item.is_done;
                                setItems((previous) => previous.map((entry) => entry.id === item.id ? { ...entry, is_done: nextDone } : entry));
                                try {
                                    await updateMyDeskTodo(item.id, { is_done: nextDone });
                                } catch {
                                }
                            }}
                        />
                    </ListItem>
                ))}
            </List>
        </Paper>
    );
}
