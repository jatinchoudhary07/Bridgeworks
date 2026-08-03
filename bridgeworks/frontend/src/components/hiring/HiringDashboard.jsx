import React from 'react';
import { useLocation } from 'react-router-dom';
import HiringJobsBoard from './HiringJobsBoard';
import HiringPipeline from './HiringPipeline';

export default function HiringDashboard() {
    const location = useLocation();
    const path = location.pathname;

    if (path.startsWith('/team/hiring/pipeline')) return <HiringPipeline />;

    return <HiringJobsBoard />;
}
