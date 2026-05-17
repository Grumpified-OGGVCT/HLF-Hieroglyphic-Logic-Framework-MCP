CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    avatar_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'offline',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_users_status CHECK (status IN ('online', 'away', 'offline'))
);

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    owner_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_workspaces_owner_id FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_workspace_members_workspace_id FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_members_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_workspace_members_workspace_user UNIQUE (workspace_id, user_id),
    CONSTRAINT chk_workspace_members_role CHECK (role IN ('admin', 'member', 'guest'))
);

CREATE TABLE IF NOT EXISTS channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'public',
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_channels_workspace_id FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_channels_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT uq_channels_workspace_slug UNIQUE (workspace_id, slug),
    CONSTRAINT chk_channels_type CHECK (type IN ('public', 'private', 'direct_message'))
);

CREATE TABLE IF NOT EXISTS channel_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL,
    user_id UUID NOT NULL,
    last_read_at TIMESTAMPTZ,
    CONSTRAINT fk_channel_members_channel_id FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    CONSTRAINT fk_channel_members_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_channel_members_channel_user UNIQUE (channel_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL,
    user_id UUID NOT NULL,
    parent_id UUID,
    content TEXT,
    type VARCHAR(20) NOT NULL DEFAULT 'text',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_messages_channel_id FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    CONSTRAINT fk_messages_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_messages_parent_id FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE SET NULL,
    CONSTRAINT chk_messages_type CHECK (type IN ('text', 'file', 'system'))
);

CREATE TABLE IF NOT EXISTS reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    user_id UUID NOT NULL,
    emoji VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_reactions_message_id FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_reactions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_reactions_message_user_emoji UNIQUE (message_id, user_id, emoji)
);

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID,
    user_id UUID NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_files_message_id FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
    CONSTRAINT fk_files_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_files_size_bytes CHECK (size_bytes >= 0)
);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type VARCHAR(30) NOT NULL,
    reference_id UUID,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_notifications_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_notifications_type CHECK (type IN ('mention', 'reply', 'workspace_invite'))
);

CREATE TABLE IF NOT EXISTS roles_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    conditions JSONB,
    CONSTRAINT uq_roles_permissions_role_resource_action UNIQUE (role_name, resource_type, action)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id);
CREATE INDEX idx_workspaces_slug ON workspaces(slug);

CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id);

CREATE INDEX idx_channels_workspace_id ON channels(workspace_id);
CREATE INDEX idx_channels_workspace_slug ON channels(workspace_id, slug);

CREATE INDEX idx_channel_members_channel_id ON channel_members(channel_id);
CREATE INDEX idx_channel_members_user_id ON channel_members(user_id);

CREATE INDEX idx_messages_channel_id ON messages(channel_id);
CREATE INDEX idx_messages_channel_created_at ON messages(channel_id, created_at);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_parent_id ON messages(parent_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_deleted_at ON messages(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_reactions_message_id ON reactions(message_id);
CREATE INDEX idx_reactions_user_id ON reactions(user_id);

CREATE INDEX idx_files_message_id ON files(message_id);
CREATE INDEX idx_files_user_id ON files(user_id);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_user_created_at ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_read_at ON notifications(read_at) WHERE read_at IS NULL;
CREATE INDEX idx_notifications_type ON notifications(type);

CREATE INDEX idx_roles_permissions_role_name ON roles_permissions(role_name);
CREATE INDEX idx_roles_permissions_resource_type ON roles_permissions(resource_type);
