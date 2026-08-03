import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Breadcrumbs,
  Link,
  Typography,
  Stack,
} from '@mui/material';
import { NavigateNext as NavigateNextIcon } from '@mui/icons-material';

export default function PageHeader({ title, subtitle, breadcrumbs = [], actions }) {
  return (
    <Box sx={{ mb: 4, userSelect: 'none' }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        spacing={2}
      >
        {/* Title and Breadcrumbs Area */}
        <Stack spacing={1}>
          {breadcrumbs && breadcrumbs.length > 0 && (
            <Breadcrumbs
              separator={<NavigateNextIcon sx={{ fontSize: '0.875rem', color: '#4D535E' }} />}
              aria-label="breadcrumb"
            >
              {breadcrumbs.map((crumb, index) => {
                const isLast = index === breadcrumbs.length - 1;
                return isLast ? (
                  <Typography
                    key={crumb.label}
                    variant="caption"
                    sx={{ color: '#8A8F98', fontWeight: 500 }}
                  >
                    {crumb.label}
                  </Typography>
                ) : (
                  <Link
                    key={crumb.label}
                    component={RouterLink}
                    to={crumb.path}
                    underline="hover"
                    sx={{
                      color: 'text.disabled',
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      '&:hover': { color: '#F7F8F8' },
                    }}
                  >
                    {crumb.label}
                  </Link>
                );
              })}
            </Breadcrumbs>
          )}

          <Stack spacing={0.5}>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                color: '#F7F8F8',
                letterSpacing: '-0.02em',
                lineHeight: 1.2,
              }}
            >
              {title}
            </Typography>
            {subtitle && (
              <Typography variant="body2" sx={{ color: '#8A8F98' }}>
                {subtitle}
              </Typography>
            )}
          </Stack>
        </Stack>

        {/* Actions Button Area */}
        {actions && (
          <Box sx={{ alignSelf: { xs: 'flex-end', sm: 'center' } }}>
            {actions}
          </Box>
        )}
      </Stack>
    </Box>
  );
}
