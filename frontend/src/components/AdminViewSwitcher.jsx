import { useEffect, useRef, useState } from 'react';
import { API_URL } from '../apiConfig';
import { clearAdminViewSession, setAdminViewSession } from '../auth/authClient';

export default function AdminViewSwitcher({ auth, user }) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState(null);
  const [clientId, setClientId] = useState('');
  const [profileId, setProfileId] = useState('staff');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open || options) return;
    let cancelled = false;
    setLoading(true);
    auth.currentUser.getIdToken()
      .then((token) => fetch(`${API_URL}/admin/preview/options`, {
        headers: { Authorization: `Bearer ${token}` },
      }))
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || 'Could not load client workspaces.');
        }
        return response.json();
      })
      .then((data) => {
        if (cancelled) return;
        setOptions(data);
        setClientId(data.schools?.[0]?.client_id || '');
      })
      .catch((requestError) => !cancelled && setError(requestError.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [auth, open, options]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', closeOutside);
    return () => document.removeEventListener('mousedown', closeOutside);
  }, [open]);

  const selectedSchool = options?.schools?.find((school) => school.client_id === clientId);
  const selectedProfile = options?.profiles?.find((profile) => profile.id === profileId);

  const startPreview = async () => {
    if (!clientId || !profileId) return;
    setLoading(true);
    setError('');
    try {
      const token = await auth.currentUser.getIdToken();
      const response = await fetch(`${API_URL}/admin/preview`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ client_id: clientId, profile_id: profileId }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Could not start preview.');
      setAdminViewSession(payload.token, payload.expires_at);
      window.location.assign('/chat');
    } catch (requestError) {
      setError(requestError.message);
      setLoading(false);
    }
  };

  const stopPreview = () => {
    clearAdminViewSession();
    window.location.assign('/admin');
  };

  if (!user?.canAdmin) return null;

  const activeAudiences = user.viewAs?.audiences || [];
  const activeProfile = options?.profiles?.find((profile) => (
    profile.audiences.length === activeAudiences.length
      && profile.audiences.every((audience) => activeAudiences.includes(audience))
  ));

  return (
    <div className="admin-view-switcher" ref={rootRef}>
      <button
        type="button"
        className={`admin-view-trigger ${user.viewAs ? 'active' : ''}`}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        {user.viewAs
          ? `Viewing ${user.school?.brand_name || user.school?.name || 'client'}`
          : 'View as client'}
        <span aria-hidden="true">⌄</span>
      </button>

      {open && (
        <div className="admin-view-menu">
          <div className="admin-view-menu-heading">
            <strong>Client preview</strong>
            <span>Private drafts and chats remain yours.</span>
          </div>

          {user.viewAs ? (
            <>
              <div className="admin-view-active">
                <span>Workspace</span>
                <strong>{user.school?.brand_name || user.school?.name}</strong>
                <span>Access</span>
                <strong>{activeProfile?.label || activeAudiences.join(', ')}</strong>
              </div>
              <button type="button" className="admin-view-stop" onClick={stopPreview}>
                Exit client view
              </button>
            </>
          ) : (
            <>
              {loading && !options ? <p>Loading workspaces…</p> : (
                <>
                  <label htmlFor="admin-preview-client">Client workspace</label>
                  <select
                    id="admin-preview-client"
                    value={clientId}
                    onChange={(event) => setClientId(event.target.value)}
                  >
                    {(options?.schools || []).map((school) => (
                      <option key={school.client_id} value={school.client_id}>
                        {school.brand_name} — {school.name}
                      </option>
                    ))}
                  </select>

                  <label htmlFor="admin-preview-profile">Access profile</label>
                  <select
                    id="admin-preview-profile"
                    value={profileId}
                    onChange={(event) => setProfileId(event.target.value)}
                  >
                    {(options?.profiles || []).map((profile) => (
                      <option key={profile.id} value={profile.id}>{profile.label}</option>
                    ))}
                  </select>

                  {selectedProfile && <p className="admin-view-description">{selectedProfile.description}</p>}
                  {selectedSchool?.document_counts && selectedProfile && (
                    <p className="admin-view-count">
                      {selectedProfile.audiences.reduce(
                        (total, audience) => total + (selectedSchool.document_counts[audience] || 0),
                        0,
                      )} visible library documents
                    </p>
                  )}
                  <button
                    type="button"
                    className="admin-view-start"
                    onClick={startPreview}
                    disabled={loading || !clientId}
                  >
                    {loading ? 'Opening…' : 'Open client view'}
                  </button>
                </>
              )}
            </>
          )}
          {error && <p className="admin-view-error">{error}</p>}
        </div>
      )}
    </div>
  );
}
