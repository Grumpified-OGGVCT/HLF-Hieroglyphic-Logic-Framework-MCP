const express = require('express');
const path = require('path');
const fs = require('fs');

function parseMultipartBody(buffer, boundary) {
  const delimiter = Buffer.from(`\r\n--${boundary}`, 'binary');
  const endDelimiter = Buffer.from(`\r\n--${boundary}--`, 'binary');
  const parts = [];

  let idx = 0;
  while (idx < buffer.length) {
    let delimIdx = buffer.indexOf(delimiter, idx);
    if (delimIdx === -1) break;

    let nextIdx = buffer.indexOf(delimiter, delimIdx + delimiter.length);
    let isLast = false;
    if (nextIdx === -1) {
      nextIdx = buffer.indexOf(endDelimiter, delimIdx + delimiter.length);
      isLast = true;
    }
    if (nextIdx === -1) break;

    let partStart = delimIdx + delimiter.length;
    let partEnd = nextIdx;

    // Skip leading CRLF after delimiter
    if (partStart + 1 < buffer.length && buffer[partStart] === 0x0d && buffer[partStart + 1] === 0x0a) {
      partStart += 2;
    }

    // Find header/body separator
    const separator = Buffer.from('\r\n\r\n', 'binary');
    const headerEnd = buffer.indexOf(separator, partStart);
    if (headerEnd === -1 || headerEnd >= partEnd) {
      idx = nextIdx + delimiter.length;
      if (isLast) break;
      continue;
    }

    const headers = buffer.slice(partStart, headerEnd).toString('binary');
    const bodyStart = headerEnd + separator.length;
    // Strip trailing CRLF before next delimiter
    let bodyEnd = partEnd;
    if (bodyEnd - 2 >= bodyStart && buffer[bodyEnd - 2] === 0x0d && buffer[bodyEnd - 1] === 0x0a) {
      bodyEnd -= 2;
    }
    const body = buffer.slice(bodyStart, bodyEnd);

    const part = { headers, body };
    const cdMatch = headers.match(/Content-Disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]+)")?/i);
    if (cdMatch) {
      part.name = cdMatch[1];
      part.filename = cdMatch[2] || null;
    }
    const ctMatch = headers.match(/Content-Type:\s*([^\r\n]+)/i);
    if (ctMatch) {
      part.contentType = ctMatch[1].trim();
    }
    parts.push(part);

    idx = nextIdx + delimiter.length;
    if (isLast) break;
  }

  return parts;
}

function multipartMiddleware(req, res, next) {
  const contentType = req.headers['content-type'] || '';
  if (!contentType.includes('multipart/form-data')) {
    return next();
  }

  const boundaryMatch = contentType.match(/boundary=([^;\s]+)/);
  if (!boundaryMatch) {
    return res.status(400).json({ error: 'Missing multipart boundary' });
  }

  const boundary = boundaryMatch[1];
  const chunks = [];

  req.on('data', (chunk) => chunks.push(chunk));
  req.on('end', () => {
    const buffer = Buffer.concat(chunks);
    const parts = parseMultipartBody(buffer, boundary);
    if (!parts) {
      return res.status(400).json({ error: 'Invalid multipart payload' });
    }

    const filePart = parts.find((p) => p.filename);
    if (filePart) {
      req.file = {
        originalname: filePart.filename,
        mimetype: filePart.contentType || 'application/octet-stream',
        buffer: filePart.body,
        size: filePart.body.length,
      };
    }

    req.body = {};
    for (const part of parts) {
      if (!part.filename && part.name) {
        req.body[part.name] = part.body.toString('utf8');
      }
    }

    next();
  });

  req.on('error', (err) => next(err));
}

function createFileRoutes(fileService, authMiddleware) {
  const router = express.Router();

  router.post('/', authMiddleware.authenticate, multipartMiddleware, async (req, res, next) => {
    try {
      let fileBuffer;
      let originalName;
      let mimeType;
      let sizeBytes;

      if (req.file) {
        fileBuffer = req.file.buffer;
        originalName = req.file.originalname;
        mimeType = req.file.mimetype;
        sizeBytes = req.file.size;
      } else if (req.body && req.body.data) {
        const base64Data = req.body.data;
        const matches = base64Data.match(/^data:([^;]+);base64,(.+)$/);
        if (matches) {
          mimeType = matches[1];
          fileBuffer = Buffer.from(matches[2], 'base64');
        } else {
          fileBuffer = Buffer.from(base64Data, 'base64');
          mimeType = req.body.mimeType || 'application/octet-stream';
        }
        originalName = req.body.filename || 'upload';
        sizeBytes = fileBuffer.length;
      } else {
        return res.status(400).json({ error: 'No file provided' });
      }

      const userId = req.user && (req.user.sub || req.user.id);
      if (!userId) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const fileRecord = await fileService.create({
        fileBuffer,
        originalName,
        mimeType,
        sizeBytes,
        userId,
        messageId: req.body.messageId || null,
      });

      res.status(201).json(fileRecord);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id', authMiddleware.authenticate, async (req, res, next) => {
    try {
      const file = await fileService.findById(req.params.id);
      if (!file) {
        return res.status(404).json({ error: 'File not found' });
      }

      const fullPath = path.join(fileService.storagePath || '.', file.storage_path);
      const safePath = path.resolve(fullPath);
      const safeRoot = path.resolve(fileService.storagePath || '.');
      if (!safePath.startsWith(safeRoot)) {
        return res.status(403).json({ error: 'Invalid file path' });
      }

      res.setHeader('Content-Type', file.mime_type);
      res.setHeader('Content-Disposition', `attachment; filename="${file.original_name}"`);
      res.setHeader('Content-Length', file.size_bytes);

      const stream = fs.createReadStream(safePath);
      stream.on('error', (err) => {
        if (err.code === 'ENOENT') {
          return res.status(404).json({ error: 'File not found on disk' });
        }
        next(err);
      });
      stream.pipe(res);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id', authMiddleware.authenticate, async (req, res, next) => {
    try {
      const removed = await fileService.remove(req.params.id);
      if (!removed) {
        return res.status(404).json({ error: 'File not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createFileRoutes };
