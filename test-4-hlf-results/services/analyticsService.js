const dataStore = require('../dataStore');

// Get all analytics data
const getAnalytics = () => {
  return { ...dataStore.analytics };
};

// Get user growth over time (simplified)
const getUserGrowth = () => {
  return dataStore.analytics.dailyActiveUsers;
};

// Increment active users (demo)
const trackPageView = () => {
  // In a real service this would log activity
  console.log('Page view tracked');
  return { success: true };
};

module.exports = {
  getAnalytics,
  getUserGrowth,
  trackPageView
};
