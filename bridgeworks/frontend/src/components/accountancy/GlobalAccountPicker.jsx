import React, { useState, useEffect } from 'react';
import { Autocomplete, TextField, Box, Typography, CircularProgress } from '@mui/material';
import { apiClient } from '../../apiClient';

const fmt = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const CLASS_LABELS = {
  bank: 'Bank Accounts',
  cash: 'Cash Accounts',
  wallet: 'Wallet Accounts',
  settlement: 'Settlement Accounts'
};

export default function GlobalAccountPicker({ value, onChange, label = "Select Financial Account", required = false, filterClass = null, ...props }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    
    apiClient('/api/accounting/financial-accounts/', { credentials: 'include' })
      .then(res => res.json())
      .then(payload => {
        if (active && payload?.success && Array.isArray(payload.data)) {
          let list = payload.data.filter(acc => acc.status === 'active');
          if (filterClass) {
            list = list.filter(acc => acc.account_class === filterClass);
          }
          setAccounts(list);
        }
      })
      .catch(err => {
        console.error('Failed to load accounts for picker:', err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filterClass]);

  // Find the selected option object
  const selectedOption = accounts.find(acc => acc.id === value) || null;

  return (
    <Autocomplete
      id="global-account-picker"
      options={accounts.sort((a, b) => a.account_class.localeCompare(b.account_class))}
      groupBy={(option) => CLASS_LABELS[option.account_class] || option.account_class}
      getOptionLabel={(option) => `${option.account_name} (${option.account_type})`}
      value={selectedOption}
      onChange={(event, newValue) => {
        if (onChange) {
          onChange(newValue ? newValue.id : '');
        }
      }}
      loading={loading}
      isOptionEqualToValue={(option, val) => option.id === val.id}
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.id} sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <Box>
            <Typography variant="body2" fontWeight="600">{option.account_name}</Typography>
            <Typography variant="caption" color="text.secondary">{option.account_type}</Typography>
          </Box>
          <Typography variant="body2" fontWeight="bold" color={option.balance < 0 ? 'error.main' : 'text.primary'}>
            {fmt(option.balance)}
          </Typography>
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          variant="outlined"
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {loading ? <CircularProgress color="inherit" size={20} /> : null}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
      {...props}
    />
  );
}
