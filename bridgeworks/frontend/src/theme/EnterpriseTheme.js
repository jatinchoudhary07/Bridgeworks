import { createTheme } from '@mui/material/styles';

export const getEnterpriseTheme = (mode) => createTheme({
  palette: {
    mode,
    primary: {
      main: '#5E6AD2', // Linear indigo accent
      light: '#7B88EB',
      dark: '#4550B4',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#00D1FF', // Electric teal
      light: '#33DAFF',
      dark: '#0092B2',
      contrastText: mode === 'dark' ? '#0A0A0A' : '#FFFFFF',
    },
    background: {
      default: mode === 'dark' ? '#0A0A0C' : '#F4F5F7', // Deep charcoal vs light cool grey
      paper: mode === 'dark' ? '#121214' : '#FFFFFF',   // Elevated dark vs clean white
    },
    text: {
      primary: mode === 'dark' ? '#F7F8F8' : '#1A1D20',   // High-contrast near-white vs dark charcoal
      secondary: mode === 'dark' ? '#8A8F98' : '#626875', // Muted grey vs medium grey
      disabled: mode === 'dark' ? '#4D535E' : '#959CA6',
    },
    action: {
      active: mode === 'dark' ? '#8A8F98' : '#626875',
      hover: mode === 'dark' ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)',
      selected: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
      disabled: mode === 'dark' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
      disabledBackground: mode === 'dark' ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
      focus: mode === 'dark' ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
    },
    divider: mode === 'dark' ? 'rgba(255, 255, 255, 0.07)' : 'rgba(0, 0, 0, 0.08)', // Subtle borders
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    h2: { fontSize: '2rem', fontWeight: 600, letterSpacing: '-0.02em', color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    h3: { fontSize: '1.5rem', fontWeight: 600, letterSpacing: '-0.01em', color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    h4: { fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.01em', color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    h5: { fontSize: '1rem', fontWeight: 600, color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    h6: { fontSize: '0.875rem', fontWeight: 600, color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    body1: { fontSize: '0.875rem', lineHeight: 1.5, color: mode === 'dark' ? '#F7F8F8' : '#1A1D20' },
    body2: { fontSize: '0.75rem', lineHeight: 1.4, color: mode === 'dark' ? '#8A8F98' : '#626875' },
    button: { textTransform: 'none', fontWeight: 500, fontSize: '0.8125rem' },
  },
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: mode === 'dark' ? '#0A0A0C' : '#F4F5F7',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
          margin: 0,
          fontFamily: '"Inter", "Roboto", sans-serif',
          scrollbarWidth: 'thin',
          '&::-webkit-scrollbar': {
            width: '6px',
            height: '6px',
          },
          '&::-webkit-scrollbar-track': {
            background: mode === 'dark' ? '#0A0A0C' : '#F4F5F7',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: mode === 'dark' ? '#262629' : '#D0D4DC',
            borderRadius: '3px',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '5px',
          boxShadow: 'none',
          padding: '6px 12px',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          '&:hover': {
            boxShadow: 'none',
          },
        },
        containedPrimary: {
          background: 'linear-gradient(180deg, #5E6AD2 0%, #4D58C2 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          color: '#FFFFFF',
          '&:hover': {
            background: 'linear-gradient(180deg, #6E7BE2 0%, #5E6AD2 100%)',
          },
        },
        outlined: {
          borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
          backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.02)',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
          '&:hover': {
            borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)',
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
          },
        },
        text: {
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
          '&:hover': {
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'dark' ? '#121214' : '#FFFFFF',
          backgroundImage: 'none',
          border: mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.07)' : '1px solid rgba(0, 0, 0, 0.06)',
          borderRadius: '8px',
          boxShadow: mode === 'dark' ? '0 4px 24px rgba(0, 0, 0, 0.4)' : '0 4px 20px rgba(0, 0, 0, 0.05)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'dark' ? '#121214' : '#FFFFFF',
          backgroundImage: 'none',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.01)',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
            transition: 'border-color 0.15s ease',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#5E6AD2',
            borderWidth: '1px',
          },
        },
        input: {
          padding: '8px 12px',
          fontSize: '0.875rem',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.05)',
          padding: '10px 16px',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
        },
        head: {
          backgroundColor: mode === 'dark' ? '#0E0E10' : '#F9FAFB',
          color: mode === 'dark' ? '#8A8F98' : '#626875',
          fontWeight: 600,
          fontSize: '0.75rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.07)' : 'rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          backgroundColor: mode === 'dark' ? '#121214' : '#FFFFFF',
          border: mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: mode === 'dark' ? '0 10px 30px rgba(0, 0, 0, 0.5)' : '0 10px 24px rgba(0, 0, 0, 0.1)',
          borderRadius: '6px',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          fontSize: '0.8125rem',
          padding: '8px 12px',
          borderRadius: '4px',
          margin: '0 4px',
          transition: 'all 0.1s ease',
          color: mode === 'dark' ? '#F7F8F8' : '#1A1D20',
          '&:hover': {
            backgroundColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(94, 106, 210, 0.15)',
            color: '#7B88EB',
            '&:hover': {
              backgroundColor: 'rgba(94, 106, 210, 0.2)',
            },
          },
        },
      },
    },
  },
});

const EnterpriseTheme = getEnterpriseTheme('dark');
export default EnterpriseTheme;
