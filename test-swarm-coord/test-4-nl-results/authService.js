const crypto = require('crypto');
const fs = require('fs');

// File path for user storage
const USERS_FILE = './users.json';

// Helper: read users from file
function readUsers() {
  try {
    const data = fs.readFileSync(USERS_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (err) {
    // If file doesn't exist or is invalid, return empty array
    return [];
  }
}

// Helper: write users to file
function writeUsers(users) {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
}

// Hash password with salt using PBKDF2
function hashPassword(password, salt) {
  const iterations = 100000;
  const keyLen = 64;
  const digest = 'sha512';
  const hash = crypto.pbkdf2Sync(password, salt, iterations, keyLen, digest);
  return {
    salt: salt || crypto.randomBytes(16).toString('hex'),
    hash: hash.toString('hex')
  };
}

// Verify password against stored hash
function verifyPassword(password, salt, storedHash) {
  const { hash } = hashPassword(password, salt);
  return hash === storedHash;
}

// Generate a simple JWT-like token using HMAC
const TOKEN_SECRET = process.env.TOKEN_SECRET || 'default-secret-change-me';

function generateToken(payload) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify({ ...payload, iat: Date.now() })).toString('base64url');
  const signature = crypto.createHmac('sha256', TOKEN_SECRET)
    .update(header + '.' + body)
    .digest('base64url');
  return `${header}.${body}.${signature}`;
}

function verifyToken(token) {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const [headerB64, bodyB64, signatureB64] = parts;
  const expectedSig = crypto.createHmac('sha256', TOKEN_SECRET)
    .update(headerB64 + '.' + bodyB64)
    .digest('base64url');
  if (expectedSig !== signatureB64) return null;
  // Decode payload
  const payload = JSON.parse(Buffer.from(bodyB64, 'base64url').toString());
  // Check token not expired (optional, e.g., 24h expiry)
  if (payload.exp && Date.now() > payload.exp) return null;
  return payload;
}

/**
 * Register a new user
 * @param {string} username
 * @param {string} password
 * @returns {{success: boolean, message: string}}
 */
function register(username, password) {
  if (!username || !password) {
    return { success: false, message: 'Username and password are required.' };
  }
  const users = readUsers();
  const existing = users.find(u => u.username === username);
  if (existing) {
    return { success: false, message: 'Username already exists.' };
  }
  const { salt, hash } = hashPassword(password);
  users.push({ username, salt, hash });
  writeUsers(users);
  return { success: true, message: 'User registered successfully.' };
}

/**
 * Login a user and return a token
 * @param {string} username
 * @param {string} password
 * @returns {{success: boolean, token?: string, message: string}}
 */
function login(username, password) {
  if (!username || !password) {
    return { success: false, message: 'Username and password are required.' };
  }
  const users = readUsers();
  const user = users.find(u => u.username === username);
  if (!user || !verifyPassword(password, user.salt, user.hash)) {
    return { success: false, message: 'Invalid credentials.' };
  }
  // Generate token with 24h expiry
  const payload = { username, exp: Date.now() + 24 * 60 * 60 * 1000 };
  const token = generateToken(payload);
  return { success: true, token, message: 'Login successful.' };
}

/**
 * Verify a token and return the payload if valid
 * @param {string} token
 * @returns {{valid: boolean, payload?: object}}
 */
function verify(token) {
  const payload = verifyToken(token);
  if (!payload) {
    return { valid: false };
  }
  return { valid: true, payload };
}

// Export the AuthService functions
module.exports = {
  register,
  login,
  verify
};
