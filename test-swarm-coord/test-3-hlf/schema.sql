CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(100),
    avatar_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'away', 'offline')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- workspaces
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id);
CREATE INDEX idx_workspaces_slug ON workspaces(slug);

-- workspace_members
CREATE TABLE workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'guest')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id)
);

CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id);

-- channels
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'public' CHECK (type IN ('public', 'private', 'direct_message')),
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, slug)
);

CREATE INDEX idx_channels_workspace_id ON channels(workspace_id);
CREATE INDEX idx_channels_slug ON channels(slug);
CREATE INDEX idx_channels_type ON channels(type);

-- channel_members
CREATE TABLE channel_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_at TIMESTAMPTZ,
    UNIQUE (channel_id, user_id)
);

CREATE INDEX idx_channel_members_channel_id ON channel_members(channel_id);
CREATE INDEX idx_channel_members_user_id ON channel_members(user_id);

-- messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'text' CHECK (type IN ('text', 'file', 'system')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_messages_channel_id_created_at ON messages(channel_id, created_at);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_parent_id ON messages(parent_id);
CREATE INDEX idx_messages_deleted_at ON messages(deleted_at) WHERE deleted_at IS NULL;

-- reactions
CREATE TABLE reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (message_id, user_id, emoji)
);

CREATE INDEX idx_reactions_message_id ON reactions(message_id);
CREATE INDEX idx_reactions_user_id ON reactions(user_id);

-- files
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_files_message_id ON files(message_id);
CREATE INDEX idx_files_user_id ON files(user_id);
CREATE INDEX idx_files_mime_type ON files(mime_type);

-- notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('mention', 'reply', 'workspace_invite')),
    reference_id UUID NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id_created_at ON notifications(user_id, created_at);
CREATE INDEX idx_notifications_user_id_read_at ON notifications(user_id, read_at);
CREATE INDEX idx_notifications_reference_id ON notifications(reference_id);

-- roles_permissions
CREATE TABLE roles_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    conditions JSONB,
    UNIQUE (role_name, resource_type, action)
);

CREATE INDEX idx_roles_permissions_role_name ON roles_permissions(role_name);
CREATE INDEX idx_roles_permissions_resource_type_action ON roles_permissions(resource_type, action);
