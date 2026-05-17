const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_MIME_PATTERNS = [
  /^image\/.*/,
  /^application\/pdf$/,
  /^text\/.*/,
  /^video\/.*/,
  /^audio\/.*/,
];

function isAllowedMimeType(mimeType) {
  return ALLOWED_MIME_PATTERNS.some((pattern) => pattern.test(mimeType));
}

function generateUuid() {
  return crypto.randomUUID();
}

function createFileService({ knex, storagePath }) {
  async function create({ fileBuffer, originalName, mimeType, sizeBytes, userId, messageId = null }) {
    if (!Buffer.isBuffer(fileBuffer)) {
      const err = new Error('fileBuffer must be a Buffer');
      err.statusCode = 400;
      throw err;
    }

    if (!originalName || typeof originalName !== 'string') {
      const err = new Error('originalName is required');
      err.statusCode = 400;
      throw err;
    }

    if (!mimeType || typeof mimeType !== 'string') {
      const err = new Error('mimeType is required');
      err.statusCode = 400;
      throw err;
    }

    if (!isAllowedMimeType(mimeType)) {
      const err = new Error('File type not allowed');
      err.statusCode = 400;
      throw err;
    }

    const actualSize = fileBuffer.length;
    if (actualSize > MAX_FILE_SIZE) {
      const err = new Error('File exceeds maximum size of 10MB');
      err.statusCode = 413;
      throw err;
    }

    const fileId = generateUuid();
    const ext = path.extname(originalName) || '';
    const storageFileName = `${fileId}${ext}`;
    const fullStoragePath = path.join(storagePath, storageFileName);

    await fs.promises.mkdir(storagePath, { recursive: true });
    await fs.promises.writeFile(fullStoragePath, fileBuffer);

    const [fileRecord] = await knex('files')
      .insert({
        id: fileId,
        message_id: messageId,
        user_id: userId,
        original_name: originalName,
        storage_path: storageFileName,
        mime_type: mimeType,
        size_bytes: actualSize,
      })
      .returning('*');

    return fileRecord;
  }

  async function findById(id) {
    const file = await knex('files').where({ id }).first();
    return file || null;
  }

  async function findByMessageId(messageId) {
    const files = await knex('files').where({ message_id: messageId }).orderBy('created_at', 'asc');
    return files;
  }

  async function remove(id) {
    const file = await findById(id);
    if (!file) {
      return false;
    }

    const fullStoragePath = path.join(storagePath, file.storage_path);
    try {
      await fs.promises.unlink(fullStoragePath);
    } catch (err) {
      if (err.code !== 'ENOENT') {
        throw err;
      }
    }

    const count = await knex('files').where({ id }).del();
    return count > 0;
  }

  return {
    create,
    findById,
    findByMessageId,
    remove,
    storagePath,
  };
}

module.exports = { createFileService };
