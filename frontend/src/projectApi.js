import { API_URL } from './apiConfig';

export function formatApiError(payload) {
  const detail = payload?.detail ?? payload?.error ?? payload;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ');
  }
  return detail?.message || 'Request failed.';
}

export async function projectRequest(auth, path, options = {}) {
  const token = await auth.currentUser.getIdToken();
  const headers = {
    Authorization: `Bearer ${token}`,
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...options.headers,
  };
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(formatApiError(payload));
  }
  return response.status === 204 ? null : response.json();
}

export const listProjects = (auth) => projectRequest(auth, '/projects');

export const getProject = (auth, projectId) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}`)
);

export const createProject = (auth, project) => projectRequest(auth, '/projects', {
  method: 'POST',
  body: JSON.stringify(project),
});

export const updateProject = (auth, projectId, changes) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
);

export const archiveProject = (auth, projectId) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}`, {
    method: 'DELETE',
  })
);

export const uploadProjectSource = (auth, projectId, file) => {
  const body = new FormData();
  body.append('file', file);
  return projectRequest(
    auth,
    `/projects/${encodeURIComponent(projectId)}/sources`,
    { method: 'POST', body },
  );
};

export const deleteProjectSource = (auth, projectId, sourceId) => (
  projectRequest(
    auth,
    `/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}`,
    { method: 'DELETE' },
  )
);

export const getProjectDraft = (auth, projectId) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}/draft`)
);

export const saveProjectDraft = (auth, projectId, markdown, reason = 'manual save') => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}/draft`, {
    method: 'PUT',
    body: JSON.stringify({ markdown, reason }),
  })
);

export const listProjectDraftVersions = (auth, projectId) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}/draft/versions`)
);

export const restoreProjectDraftVersion = (auth, projectId, version) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}/draft/restore`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
);

export const createProjectChat = (auth, projectId, chat = {}) => (
  projectRequest(auth, `/projects/${encodeURIComponent(projectId)}/chats`, {
    method: 'POST',
    body: JSON.stringify(chat),
  })
);

export const getProjectChat = (auth, projectId, chatId) => (
  projectRequest(
    auth,
    `/projects/${encodeURIComponent(projectId)}/chats/${encodeURIComponent(chatId)}`,
  )
);

export const deleteProjectChat = (auth, projectId, chatId) => (
  projectRequest(
    auth,
    `/projects/${encodeURIComponent(projectId)}/chats/${encodeURIComponent(chatId)}`,
    { method: 'DELETE' },
  )
);
