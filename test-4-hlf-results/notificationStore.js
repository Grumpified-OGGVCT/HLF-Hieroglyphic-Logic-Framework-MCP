const notifications = [];
let nextId = 1;

module.exports = {
  addNotification(userId, message, type = 'info') {
    const notification = {
      id: nextId++,
      userId,
      message,
      type,
      read: false,
      createdAt: new Date().toISOString()
    };
    notifications.push(notification);
    return notification;
  },

  getNotificationsByUser(userId) {
    return notifications.filter(n => n.userId === userId);
  },

  markAsRead(notificationId) {
    const notification = notifications.find(n => n.id === notificationId);
    if (notification) {
      notification.read = true;
      return notification;
    }
    return null;
  },

  // For debugging or admin purposes
  getAll() {
    return notifications;
  }
};