// In-memory data store with initial mock data

const users = [
  { id: 1, username: 'alice', email: 'alice@example.com', role: 'user', status: 'active' },
  { id: 2, username: 'bob', email: 'bob@example.com', role: 'user', status: 'active' },
  { id: 3, username: 'charlie', email: 'charlie@example.com', role: 'moderator', status: 'active' },
  { id: 4, username: 'dave', email: 'dave@example.com', role: 'user', status: 'banned' }
];

const reports = [
  { id: 1, contentId: 'post-123', reporterId: 1, reason: 'spam', status: 'pending', createdAt: new Date('2025-03-20') },
  { id: 2, contentId: 'post-456', reporterId: 2, reason: 'harassment', status: 'resolved', createdAt: new Date('2025-03-21') }
];

const analytics = {
  totalUsers: 4,
  activeUsers: 3,
  bannedUsers: 1,
  totalReports: 2,
  pendingReports: 1,
  resolvedReports: 1,
  recentRegistrations: [
    { username: 'eve', date: new Date('2025-03-22') }
  ],
  dailyActiveUsers: [
    { date: '2025-03-20', count: 2 },
    { date: '2025-03-21', count: 3 },
    { date: '2025-03-22', count: 4 }
  ]
};

let nextUserId = 5;
let nextReportId = 3;

module.exports = {
  users,
  reports,
  analytics,
  nextUserId,
  nextReportId
};
