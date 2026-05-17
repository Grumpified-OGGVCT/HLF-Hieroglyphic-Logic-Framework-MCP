# Natural Language Swarm: 15-Agent Real-Time Chat Platform

## Task: Build a Complete Real-Time Chat API (Slack/Discord-like)

**Tech Stack:** Node.js + Express + PostgreSQL + Knex + Socket.io + Redis + JWT
**Goal:** Working chat API with real-time messaging, channels, DMs, file uploads, presence, search, notifications, and permissions.

---

## Agent Instructions

### Agent 1: SchemaDesigner
Design PostgreSQL schema for a chat platform.

**Tables:**
- `users` (id, username, email, password_hash, avatar_url, status [online|away|offline], last_seen, created_at)
- `workspaces` (id, name, slug, owner_id, created_at)
- `workspace_members` (workspace_id, user_id, role [owner|admin|member], joined_at)
- `channels` (id, workspace_id, name, type [public|private|dm], created_by, created_at)
- `channel_members` (channel_id, user_id, joined_at, last_read_message_id)
- `messages` (id, channel_id, user_id, content, type [text|file|system], parent_id [thread], edited_at, created_at)
- `reactions` (message_id, user_id, emoji, created_at)
- `files` (id, message_id, filename, mime_type, size, url, created_at)
- `notifications` (id, user_id, type [mention|dm|channel], reference_id, read, created_at)
- `roles_permissions` (workspace_id, role, permission, created_at)

**Write:** `migrations/001_initial_schema.js`, `schema.sql`

### Agent 2: MigrationWriter
Write complete Knex migrations for all tables with indexes, foreign keys, and check constraints.

**Input:** `migrations/001_initial_schema.js`, `schema.sql`
**Write:** `migrations/002_indexes.js`, `migrations/003_constraints.js`

### Agent 3: UserService
Build user management module.

**Input:** `schema.sql`
**Write:** `services/userService.js` - CRUD, profile updates, avatar, status changes, search users
**Write:** `routes/users.js` - user endpoints

### Agent 4: AuthService
Build JWT + refresh token auth with bcrypt.

**Input:** `services/userService.js`
**Write:** `services/authService.js` - register, login, logout, refresh, verify
**Write:** `middleware/auth.js` - authenticate, optionalAuth

### Agent 5: WorkspaceService
Build workspace (team/organization) management.

**Input:** `schema.sql`, `services/userService.js`
**Write:** `services/workspaceService.js` - create, invite, join, leave, list
**Write:** `routes/workspaces.js`

### Agent 6: ChannelService
Build channel management (public, private, DM).

**Input:** `schema.sql`, `services/workspaceService.js`
**Write:** `services/channelService.js` - create, join, leave, archive, list members
**Write:** `routes/channels.js`

### Agent 7: MessageService
Build message CRUD with threading and reactions.

**Input:** `schema.sql`, `services/channelService.js`
**Write:** `services/messageService.js` - send, edit, delete, thread replies, add/remove reactions, history, search in channel
**Write:** `routes/messages.js`

### Agent 8: WebSocketEngine
Build Socket.io real-time messaging.

**Input:** `services/messageService.js`, `services/channelService.js`
**Write:** `websocket/engine.js` - connection handling, join/leave rooms, broadcast messages, typing indicators, presence updates
**Write:** `websocket/events.js` - event constants and handlers

### Agent 9: FileUploadService
Build file upload handling with mime type validation.

**Input:** `schema.sql`
**Write:** `services/fileService.js` - upload, validate mime type, max size check, generate URL, delete
**Write:** `routes/files.js`

### Agent 10: PresenceService
Build online/offline/away status and typing indicators.

**Input:** `services/userService.js`
**Write:** `services/presenceService.js` - update status, get online users, typing indicators
**Write:** `routes/presence.js`

### Agent 11: NotificationService
Build push/email notification system.

**Input:** `schema.sql`, `services/messageService.js`
**Write:** `services/notificationService.js` - create notification, mark read, get unread count, mention detection
**Write:** `routes/notifications.js`

### Agent 12: SearchService
Build message search with full-text search.

**Input:** `services/messageService.js`, `schema.sql`
**Write:** `services/searchService.js` - search messages by text, by user, by channel, by date range, pagination
**Write:** `routes/search.js`

### Agent 13: PermissionService
Build role-based access control (RBAC).

**Input:** `schema.sql`, `services/workspaceService.js`, `services/channelService.js`
**Write:** `services/permissionService.js` - check permissions, assign roles, workspace/channel-level ACL
**Write:** `middleware/permissions.js` - requirePermission, requireRole

### Agent 14: RateLimitService
Build API rate limiting per user and per endpoint.

**Write:** `services/rateLimitService.js` - sliding window counter, Redis-backed, configurable per endpoint
**Write:** `middleware/rateLimit.js` - apply rate limits to routes

### Agent 15: DevOpsAssembler
Create server entry point, package.json, docker-compose, config.

**Input:** ALL previous agents' outputs
**Write:** `server.js`, `package.json`, `knexfile.js`, `.env.example`, `.gitignore`, `docker-compose.yml`, `Dockerfile`

---

## Critical Rules
1. Every agent MUST read files from agents they depend on
2. Every agent MUST write to their assigned files only
3. If you find a bug in another agent's code, document it in BUGS.md and work around it
4. Use CommonJS (require/module.exports) for compatibility
5. Do NOT install packages - just write the code

## Execution Order
1. Agent 1 (SchemaDesigner) - no deps
2. Agent 2 (MigrationWriter) - depends on Agent 1
3. Agents 3 (UserService), 4 (AuthService) - parallel after schema ready
4. Agents 5 (WorkspaceService), 6 (ChannelService) - parallel after user/auth
5. Agents 7 (MessageService), 8 (WebSocketEngine), 9 (FileUploadService), 10 (PresenceService), 11 (NotificationService) - parallel after channels
6. Agents 12 (SearchService), 13 (PermissionService), 14 (RateLimitService) - parallel after messages/workspace
7. Agent 15 (DevOpsAssembler) - after everything
