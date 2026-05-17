const dataStore = require('../dataStore');

// Get all reports
const getAllReports = () => {
  return dataStore.reports;
};

// Create a new report
const createReport = (contentId, reporterId, reason) => {
  const newReport = {
    id: dataStore.nextReportId++,
    contentId,
    reporterId,
    reason,
    status: 'pending',
    createdAt: new Date()
  };
  dataStore.reports.push(newReport);
  dataStore.analytics.totalReports++;
  dataStore.analytics.pendingReports++;
  return newReport;
};

// Resolve a report
const resolveReport = (reportId) => {
  const report = dataStore.reports.find(r => r.id === reportId);
  if (!report) return null;
  report.status = 'resolved';
  dataStore.analytics.pendingReports = Math.max(0, dataStore.analytics.pendingReports - 1);
  dataStore.analytics.resolvedReports++;
  return report;
};

// Ban a user
const banUser = (userId) => {
  const user = dataStore.users.find(u => u.id === userId);
  if (!user) return null;
  user.status = 'banned';
  dataStore.analytics.activeUsers = Math.max(0, dataStore.analytics.activeUsers - 1);
  dataStore.analytics.bannedUsers++;
  return user;
};

// Unban a user
const unbanUser = (userId) => {
  const user = dataStore.users.find(u => u.id === userId);
  if (!user) return null;
  user.status = 'active';
  dataStore.analytics.activeUsers++;
  dataStore.analytics.bannedUsers = Math.max(0, dataStore.analytics.bannedUsers - 1);
  return user;
};

module.exports = {
  getAllReports,
  createReport,
  resolveReport,
  banUser,
  unbanUser
};
