import React, { createContext, useContext, useEffect, useState, useMemo } from "react";
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

const ThemeContext = createContext(null);

export function CustomThemeProvider({ children }) {
    //get theme from local storage
    const [mode, setMode] = useState(() => {
        return localStorage.getItem('theme') || 'light';
    });
    //set theme to local storage
    useEffect(() => {
        localStorage.setItem('theme', mode);
        // Update document background
        document.documentElement.setAttribute('data-theme', mode);
    }, [mode]);

    const toggleTheme = () => {
        setMode((prevMode) => (prevMode === 'light' ? 'dark' : 'light'));
    }
    const theme = useMemo(
        () =>
            createTheme({
                palette: {
                    mode,
                    ...(mode === 'light'
                        ? {
                            // Light mode
                            primary: {
                                main: '#1976d2',
                            },
                            secondary: {
                                main: '#dc004e',
                            },
                            background: {
                                default: '#f5f5f5',
                                paper: '#ffffff',
                            },
                            text: {
                                primary: '#000000',
                                secondary: '#555555',
                            },
                        }
                        : {
                            // Dark mode
                            primary: {
                                main: '#90caf9',
                            },
                            secondary: {
                                main: '#f48fb1',
                            },
                            background: {
                                default: '#121212',
                                paper: '#1e1e1e',
                            },
                            text: {
                                primary: '#ffffff',
                                secondary: '#b0b0b0',
                            },
                        }),
                },
                components: {
                    MuiTextField: {
                        defaultProps: {
                            inputProps: { lang: 'en-GB' },
                        },
                    },
                    MuiCssBaseline: {
                        styleOverrides: {
                            body: {
                                margin: 0,
                                minHeight: '100vh',
                            },
                        },
                    },
                },
            }),
        [mode]
    );

    return (
        <ThemeContext.Provider value={{ mode, toggleTheme }}>
            <ThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </ThemeProvider>
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    return useContext(ThemeContext);
}
