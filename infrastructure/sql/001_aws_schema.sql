-- Plate AWS schema (RDS) — no Supabase auth.users dependency
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cognito_sub TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    bio TEXT,
    recipe_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profiles_username ON profiles(username);
CREATE INDEX idx_profiles_cognito_sub ON profiles(cognito_sub);

CREATE TYPE recipe_status AS ENUM (
    'uploading', 'processing', 'pending_review', 'approved',
    'rejected', 'published'
);

CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status recipe_status DEFAULT 'uploading',
    moderation_decision TEXT,
    moderation_reason TEXT,
    like_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recipes_user_id ON recipes(user_id);
CREATE INDEX idx_recipes_status ON recipes(status);
CREATE INDEX idx_recipes_created_at ON recipes(created_at DESC);

CREATE TABLE recipe_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    public_url TEXT,
    sort_order INT DEFAULT 0,
    is_primary BOOLEAN DEFAULT TRUE,
    width INT,
    height INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recipe_images_recipe ON recipe_images(recipe_id);

CREATE TABLE likes (
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, recipe_id)
);

CREATE INDEX idx_likes_recipe ON likes(recipe_id);

CREATE OR REPLACE FUNCTION bump_like_count() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE recipes SET like_count = like_count + 1 WHERE id = NEW.recipe_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE recipes SET like_count = GREATEST(like_count - 1, 0) WHERE id = OLD.recipe_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_likes_count
AFTER INSERT OR DELETE ON likes
FOR EACH ROW EXECUTE FUNCTION bump_like_count();

CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_recipe ON comments(recipe_id);

CREATE OR REPLACE FUNCTION bump_comment_count() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE recipes SET comment_count = comment_count + 1 WHERE id = NEW.recipe_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE recipes SET comment_count = GREATEST(comment_count - 1, 0) WHERE id = OLD.recipe_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_comments_count
AFTER INSERT OR DELETE ON comments
FOR EACH ROW EXECUTE FUNCTION bump_comment_count();

CREATE TYPE job_status AS ENUM ('queued', 'running', 'completed', 'failed');

CREATE TABLE moderation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    status job_status DEFAULT 'queued',
    current_step TEXT,
    progress FLOAT DEFAULT 0,
    decision TEXT,
    detections JSONB,
    moderation_scores JSONB,
    sqs_message_id TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_moderation_jobs_status ON moderation_jobs(status);
CREATE INDEX idx_moderation_jobs_recipe ON moderation_jobs(recipe_id);
CREATE INDEX idx_moderation_jobs_sqs ON moderation_jobs(sqs_message_id);

CREATE TABLE review_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    priority INT DEFAULT 0,
    review_status TEXT DEFAULT 'pending',
    reviewer_notes TEXT,
    detections JSONB,
    moderation_scores JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

CREATE INDEX idx_review_queue_status ON review_queue(review_status);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES profiles(id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

CREATE OR REPLACE FUNCTION bump_recipe_count() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'published' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'published') THEN
        UPDATE profiles SET recipe_count = recipe_count + 1 WHERE id = NEW.user_id;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'published' AND NEW.status <> 'published' THEN
        UPDATE profiles SET recipe_count = GREATEST(recipe_count - 1, 0) WHERE id = OLD.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recipe_count
AFTER INSERT OR UPDATE OF status ON recipes
FOR EACH ROW EXECUTE FUNCTION bump_recipe_count();
