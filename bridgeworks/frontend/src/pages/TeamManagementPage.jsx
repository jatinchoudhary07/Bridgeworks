import React from "react";
import { Box } from "@mui/material";
import { useLocation } from "react-router-dom";
import { TeamInviteForm } from "../components/forms";
import HumanResourcesSidebar from "../components/humanResources/HumanResourcesSidebar";
import MasterWorkforceSheet from "../components/humanResources/MasterWorkforceSheet";
import RoleEditor from "../components/humanResources/RoleEditor";
import HRAttendanceDashboard from "../components/humanResources/HRAttendanceDashboard";
import HRPayrollDashboard from "../components/humanResources/HRPayrollDashboard";
import HRExpensesTracker from "../components/humanResources/HRExpensesTracker";
import WorkforceHierarchyTree from "../components/humanResources/WorkforceHierarchyTree";
import HRDiaryLogbooks from "../components/humanResources/HRDiaryLogbooks";
import HRMasterTaskTracker from "../components/humanResources/HRMasterTaskTracker";
import HRMeetingManager from "../components/humanResources/HRMeetingManager";
import DepartmentExpenseTracker from "../components/common/DepartmentExpenseTracker";
import HRAnalyticsDashboard from "../components/humanResources/HRAnalyticsDashboard";
import HiringDashboard from "../components/hiring/HiringDashboard";
import TrainingHubSection from "../components/mydesk/sections/TrainingHubSection";

export default function TeamManagementPage() {
  const location = useLocation();
  const isMasterWorkforceRoute = location.pathname.startsWith('/team/master-workforce-sheet')
    || location.pathname.startsWith('/team/master-inventory-sheet');
  const isMasterTaskTrackerRoute = location.pathname.startsWith('/team/master-task-tracker');
  const isMeetingManagerRoute = location.pathname.startsWith('/team/meeting-manager');
  const isRoleEditorRoute = location.pathname.startsWith('/team/role-editor');
  const isAttendanceRoute = location.pathname.startsWith('/team/attendance');
  const isHierarchyRoute = location.pathname.startsWith('/team/org-hierarchy');
  const isPayrollRoute = location.pathname.startsWith('/team/payroll');
  const isExpensesRoute = location.pathname.startsWith('/team/expenses');
  const isDeptExpensesRoute = location.pathname.startsWith('/team/dept-expenses');
  const isDiaryRoute = location.pathname.startsWith('/team/diary');
  const isAnalyticsRoute = location.pathname.startsWith('/team/analytics');
  const isHiringRoute = location.pathname.startsWith('/team/hiring');
  const isTrainingRoute = location.pathname.startsWith('/team/training');

  return (
    <Box sx={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      <HumanResourcesSidebar />

      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        {isHiringRoute
          ? <HiringDashboard />
          : isAnalyticsRoute
          ? <HRAnalyticsDashboard />
          : isMasterWorkforceRoute
          ? <MasterWorkforceSheet />
          : isMasterTaskTrackerRoute
            ? <HRMasterTaskTracker />
            : isMeetingManagerRoute
              ? <HRMeetingManager />
              : isRoleEditorRoute
                ? <RoleEditor />
                : isAttendanceRoute
                  ? <HRAttendanceDashboard />
                  : isHierarchyRoute
                    ? <WorkforceHierarchyTree />
                    : isPayrollRoute
                      ? <HRPayrollDashboard />
                      : isExpensesRoute
                        ? <HRExpensesTracker />
                        : isDeptExpensesRoute
                          ? <DepartmentExpenseTracker department="Human Resources" />
                          : isDiaryRoute
                            ? <HRDiaryLogbooks />
                            : isTrainingRoute
                              ? <TrainingHubSection isAdminMode={true} />
                              : <TeamInviteForm />}
      </Box>
    </Box>
  );
}


