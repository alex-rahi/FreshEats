-- Storage buckets for recipe images (run against Supabase)

INSERT INTO storage.buckets (id, name, public)
VALUES
  ('raw-uploads', 'raw-uploads', false),
  ('recipe-images', 'recipe-images', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Authenticated users can upload raw images"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'raw-uploads');

CREATE POLICY "Public read recipe images"
ON storage.objects FOR SELECT TO public
USING (bucket_id = 'recipe-images');

CREATE POLICY "Owners can upload recipe images"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'recipe-images' AND (storage.foldername(name))[1] = auth.uid()::text);
