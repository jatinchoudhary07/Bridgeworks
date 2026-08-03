# Employee Attendance and Worked Hours Policy

**Effective Date:** June 19, 2026  
**Applicability:** All Employees and Team Members  

---

## 1. Overview and Purpose
This policy sets forth the guidelines and expectations for attendance tracking, session logging, and daily worked-hours verification. To maintain a fair, transparent, and productive work environment, our attendance system uses location-based verification (geofencing and network IP recognition) and calculates actual active worked hours rather than simple login-to-logout duration.

---

## 2. Check-In & Check-Out Protocols

All employees must record their attendance daily using the designated attendance application.

### A. Location Verification
To ensure check-ins reflect actual work presence, check-ins are verified using two signals:
1. **Office IP Verification:** Check-ins performed while connected to a registered office network or secure office subnet (Wi-Fi).
2. **GPS Geofence Verification:** Check-ins performed when your physical location (GPS coordinates) is within the registered boundary of your office location.

Based on these signals, your work mode is categorized dynamically:
* **Work from Office (WFO):** Assigned when checked in from a registered office network IP or within the geofenced boundary of the office.
* **Work from Home (WFH):** Assigned when checked in from home or outside the office radius (where authorized).
* **Dual-Signal Requirement:** Certain office locations require **both** a registered Office IP connection **and** GPS presence within the office geofence to log a Work from Office (WFO) day.

> [!WARNING]  
> If location access or GPS accuracy is low/spoofed, the system will flag the login as an anomaly. Ensure GPS location permissions are enabled on your device.

---

## 3. Session-Based Worked Hours (Net Worked Hours)

To prevent timesheet gaming (e.g., checking in early, logging out, going absent, and logging in again at the end of the day to simulate a full day's work), the system tracks actual **net worked hours**.

* **Session Summation:** The system calculates the sum of all your active attendance session durations throughout the day.
* **Break Deductions:** Any periods where you are checked out or logged out do not count towards your worked hours.
* **Multiple Sessions:** If you check out for a meeting, personal errand, or split shift, your worked hours for each active session are added together to compute your daily total.

---

## 4. Minimum Daily Worked Hours & Attendance Status

Your attendance status (Present, Half Day, or Absent) and subsequent payroll calculation are determined by your cumulative **Net Worked Hours** for the day:

| Net Worked Hours | Attendance Status | Salary/Credit | Salary Deduction |
| :--- | :--- | :--- | :--- |
| **>= 6.0 Hours** | **Full Day / Present** | 1.0 Day Credit | Nil |
| **3.0 to 5.99 Hours** | **Half Day** | 0.5 Day Credit | 0.5 Day Deduction |
| **< 3.0 Hours** | **Absent** | 0.0 Day Credit | 1.0 Day Deduction |

### Critical Status Policies:
1. **Full Day (>= 6.0 hours):** If your cumulative net worked hours across all sessions for the day is 6.0 hours or more, you receive full attendance credit.
2. **Half Day (3.0 to 5.99 hours):** If your cumulative net worked hours is between 3.0 and 6.0 hours, you will be marked as Half Day, and a 0.5-day salary deduction will apply unless covered by an approved leave.
3. **Absent (< 3.0 hours):** If your cumulative net worked hours for the day is less than 3.0 hours, you will be marked as Absent, and a full 1.0-day salary deduction will apply.

---

## 5. Session Auto-Closure & Idle Timeouts

To maintain accuracy in worked hours calculations, active sessions are subject to auto-closure under the following conditions:

* **Idle Timeouts:** If the application detects no activity (heartbeat signals) for a specified duration (typically 15 to 30 minutes, depending on your organization/profile settings), your session will be auto-closed. 
* **Midnight Auto-Logout:** If a session is left open at the end of the day, the system will automatically log you out at midnight. In such cases, the system falls back to your shift's scheduled end time in your team rulebook (e.g., 6:30 PM) to calculate the session duration.

---

## 6. Corrections and Overrides

We understand that exceptions occur (e.g., forgotten check-outs, network issues, or external client meetings).
* **HR Override:** HR Managers and Administrators have the authority to manually adjust and override attendance status or hours-worked calculations.
* **Discrepancy Resolution:** If your status is incorrectly marked as Absent or Half Day due to technical difficulties, submit an attendance regularization request to your HR department with supporting evidence of your working hours.
