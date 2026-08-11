-- Plate Initial Schema
-- Recipe sharing with YOLO image moderation

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Standalone local Postgres: create a stub auth.users so FKs work without Supabase.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'auth') THEN
    CREATE SCHEMA auth;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PROFILES
-- ============================================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    bio TEXT,
    recipe_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profiles_username ON profiles(username);

-- ============================================================
-- RECIPES
-- ============================================================
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

-- ============================================================
-- RECIPE IMAGES
-- ============================================================
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

-- ============================================================
-- LIKES
-- ============================================================
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

-- ============================================================
-- COMMENTS
-- ============================================================
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

-- ============================================================
-- MODERATION JOBS
-- ============================================================
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
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_moderation_jobs_status ON moderation_jobs(status);
CREATE INDEX idx_moderation_jobs_recipe ON moderation_jobs(recipe_id);

-- ============================================================
-- REVIEW QUEUE (manual approval for uncertain YOLO results)
-- ============================================================
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

-- ============================================================
-- AUDIT LOG
-- ============================================================
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

-- ============================================================
-- PROFILE AUTO-CREATE (Supabase auth hook)
-- ============================================================
CREATE OR REPLACE FUNCTION handle_new_user() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, username, display_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Only attach trigger if Supabase-style auth.users exists with raw_user_meta_data
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'auth' AND table_name = 'users' AND column_name = 'raw_user_meta_data'
    ) THEN
        DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION handle_new_user();
    END IF;
EXCEPTION WHEN undefined_table THEN
    NULL;
END $$;

-- Bump recipe_count on publish
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
