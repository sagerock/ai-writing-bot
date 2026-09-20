-- auth.users access for the app role through security-definer functions
-- owned by postgres (the app role cannot be granted the auth schema directly).
create or replace function romalume.auth_users()
returns table (id uuid, email text, email_verified boolean, display_name text, created_at timestamptz, last_sign_in_at timestamptz)
language sql security definer set search_path = public, auth stable as $$
  select u.id, u.email::text, u.email_confirmed_at is not null,
         (u.raw_user_meta_data->>'full_name')::text, u.created_at, u.last_sign_in_at
  from auth.users u
$$;
grant execute on function romalume.auth_users() to romalume_app;

-- Test-only helpers: throwaway users at @romalume-tests.invalid.
create or replace function romalume.test_create_auth_user(p_id uuid, p_email text)
returns void language sql security definer set search_path = public, auth as $$
  insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                          email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
  values (p_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
          p_email, '', now(), '{"provider":"email","providers":["email"]}'::jsonb,
          '{"test":true}'::jsonb, now(), now())
$$;
create or replace function romalume.test_delete_auth_user(p_id uuid)
returns void language sql security definer set search_path = public, auth as $$
  delete from auth.users where id = p_id and email like '%@romalume-tests.invalid'
$$;
grant execute on function romalume.test_create_auth_user(uuid, text) to romalume_app;
grant execute on function romalume.test_delete_auth_user(uuid) to romalume_app;
