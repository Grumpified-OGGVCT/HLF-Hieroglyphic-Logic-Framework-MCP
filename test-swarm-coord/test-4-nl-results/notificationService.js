const EventEmitter = require('events');

class NotificationService extends EventEmitter {
  constructor() {
    super();
    this.notifications = [];
  }

  /**
   * Send a notification
   * @param {Object} notification - { type, recipient, message, channel }
   * @returns {Object} the saved notification payload
   */
  send(notification) {
    const payload = {
      ...notification,
      id: this.notifications.length + 1,
      timestamp: new Date().toISOString(),
      status: 'sent'
    };
    this.notifications.push(payload);
    console.log(`[NotificationService] Sent ${notification.type} notification to ${notification.recipient}: ${notification.message}`);
    this.emit('sent', payload);
    return payload;
  }

  /**
   * Get all sent notifications
   * @returns {Array} copy of notification history
   */
  getHistory() {
    return [...this.notifications];
  }

  /**
   * Clear all notifications
   */
  clearHistory() {
    this.notifications = [];
  }
}

// Singleton instance
module.exports = new NotificationService();