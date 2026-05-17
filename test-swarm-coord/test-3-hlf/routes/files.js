const { Router } = require('express');

function createFileRoutes(fileService, authMiddleware) {
  if (!fileService) throw new Error('fileService is required');
  if (!authMiddleware) throw new Error('authMiddleware is required');

  const router = Router();

  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      // Support multipart/form-data fields if available (e.g. via multer)
      // Fallback: accept base64 string in JSON body for environments without multer
      let original_name;
      let mime_type;
      let size_bytes;
      let buffer;

      if (req.file) {
        // multer style
        original_name = req.file.originalname;
        mime_type = req.file.mimetype;
        size_bytes = req.file.size;
        buffer = req.file.buffer;
      } else if (req.body && req.body.base64) {
        const base64Data = req.body.base64;
        buffer = Buffer.from(base64Data, 'base64');
        original_name = req.body.original_name || 'upload';
        mime_type = req.body.mime_type || 'application/octet-stream';
        size_bytes = buffer.length;
      } else {
        return res.status(400).json({ error: 'No file provided. Upload multipart/form-data or JSON with base64 field.' });
      }

      const file = await fileService.create({
        message_id: req.body.message_id || null,
        user_id: req.user.id,
        original_name,
        mime_type,
        size_bytes,
        buffer,
      });

      return res.status(201).json(file);
    } catch (err) {
      return next(err);
    }
  });

  router.get('/:id', authMiddleware, async (req, res, next) => {
    try {
      const file = await fileService.findById(req.params.id);
      if (!file) {
        return res.status(404).json({ error: 'File not found' });
      }

      // Stream file to response
      const fs = require('fs');
      const path = require('path');

      if (!fs.existsSync(file.storage_path)) {
        return res.status(404).json({ error: 'File not found on disk' });
      }

      res.setHeader('Content-Type', file.mime_type);
      res.setHeader('Content-Length', file.size_bytes);
      res.setHeader('Content-Disposition', `attachment; filename="${path.basename(file.original_name)}"`);

      const stream = fs.createReadStream(file.storage_path);
      stream.on('error', (err) => next(err));
      stream.pipe(res);
    } catch (err) {
      return next(err);
    }
  });

  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const file = await fileService.remove(req.params.id);
      if (!file) {
        return res.status(404).json({ error: 'File not found' });
      }
      return res.status(200).json({ deleted: true, id: file.id });
    } catch (err) {
      return next(err);
    }
  });

  return router;
}

module.exports = { createFileRoutes };
