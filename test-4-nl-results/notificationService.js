class NotificationService {
  constructor() {
    this.log = [];
  }

  async send(type, recipient, message) {
    const validTypes = ['email', 'sms', 'push'];
    if (!validTypes.includes(type)) {
      throw new Error(`Unsupported notification type: ${type}`);
    }

    console.log(`Sending ${type} to ${recipient}: ${message}`);
    // Simulate async operation
    return new Promise((resolve) => {
      setTimeout(() => {
        const entry = { type, recipient, message, timestamp: new Date().toISOString(), status: 'sent' };
        this.log.push(entry);
        resolve({ success: true, notificationId: this.log.length, entry });
      }, 50);
    });
  }
}

module.exports = NotificationService;
