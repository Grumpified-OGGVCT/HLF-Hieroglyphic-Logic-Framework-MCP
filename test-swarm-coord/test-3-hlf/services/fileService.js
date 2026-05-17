const { randomUUID } = require('crypto');
const fs = require('fs');
const path = require('path');

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MIME_WHITELIST = [
  /^image\/.*/,
  /^application\/pdf$/,
  /^text\/.*/,
  /^video\/.*/,
  /^audio\/.*/,
];

function validateMimeType(mimeType) {
  if (typeof mimeType !== 'string') return false;
  return MIME_WHITELIST.some((pattern) => pattern.test(mimeType));
}

function validateFileSize(sizeBytes) {
  return Number.isFinite(sizeBytes) && sizeBytes > 0 && sizeBytes <= MAX_FILE_SIZE;
}

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function createFileService({ knex, storagePath }) {
  if (!knex) throw new Error('knex is required');
  if (!storagePath) throw new Error('storagePath is required');

  ensureDir(storagePath);

  async function create({ message_id, user_id, original_name, mime_type, size_bytes, buffer }) {
    if (!user_id) throw new Error('user_id is required');
    if (!original_name) throw new Error('original_name is required');
    if (!mime_type) throw new Error('mime_type is required');
    if (!buffer || !Buffer.isBuffer(buffer)) throw new Error('buffer is required');

    if (!validateMimeType(mime_type)) {
      throw new Error(`MIME type "${mime_type}" is not allowed`);
    }

    if (!validateFileSize(size_bytes)) {
      throw new Error(`File size ${size_bytes} exceeds maximum allowed size of ${MAX_FILE_SIZE} bytes`);
    }

    const id = randomUUID();
    const ext = path.extname(original_name) || '';
    const filename = `${id}${ext}`;
    const fileStoragePath = path.join(storagePath, filename);

    await fs.promises.writeFile(fileStoragePath, buffer);

    const [file] = await knex('files')
      .insert({
        id,
        message_id: message_id || null,
        user_id,
        original_name,
        storage_path: fileStoragePath,
        mime_type,
        size_bytes,
      })
      .returning('*');

    return file;
  }

  async function findById(id) {
    if (!id) return null;
    const file = await knex('files').where({ id }).first();
    return file || null;
  }

  async function findByMessageId(message_id) {
    if (!message_id) return [];
    return knex('files').where({ message_id });
  }

  async function remove(id) {
    if (!id) return null;

    const file = await findById(id);
    if (!file) return null;

    if (fs.existsSync(file.storage_path)) {
      await fs.promises.unlink(file.storage_path);
    }

    await knex('files').where({ id }).del();

    return file;
  }

  return {
    create,
    findById,
    findByMessageId,
    remove,
  };
}

module.exports = { createFileService };
