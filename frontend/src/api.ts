const jsonHeaders = {'Content-Type':'application/json'}
async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const res=await fetch(`/api${path}`,init)
  if(!res.ok){let msg=`请求失败 (${res.status})`;try{const data=await res.json();msg=data.detail||msg}catch{}throw new Error(msg)}
  return res.json()
}
export const api={
  health:()=>request<any>('/health'),
  projects:()=>request<any[]>('/projects'),
  createProject:(body:any)=>request<any>('/projects',{method:'POST',headers:jsonHeaders,body:JSON.stringify(body)}),
  project:(id:string)=>request<any>(`/projects/${id}`),
  deleteProject:(id:string)=>request<any>(`/projects/${id}`,{method:'DELETE'}),
  history:(id:string)=>request<any>(`/projects/${id}/history`),
  workspaceVersion:(projectId:string,versionId:string)=>request<any>(`/projects/${projectId}/history/${versionId}`),
  restoreWorkspaceVersion:(projectId:string,versionId:string)=>request<any>(`/projects/${projectId}/history/${versionId}/restore`,{method:'POST'}),
  prepare:(id:string)=>request<any>(`/projects/${id}/prepare`,{method:'POST'}),
  saveWorkspace:(id:string,workspace:any)=>request<any>(`/projects/${id}/workspace`,{method:'PATCH',headers:jsonHeaders,body:JSON.stringify({workspace})}),
  createDebate:(body:any)=>request<any>('/debates',{method:'POST',headers:jsonHeaders,body:JSON.stringify(body)}),
  debate:(id:string)=>request<any>(`/debates/${id}`),
  deleteDebate:(id:string)=>request<any>(`/debates/${id}`,{method:'DELETE'}),
  turn:(id:string,body:any)=>request<any>(`/debates/${id}/turns`,{method:'POST',headers:jsonHeaders,body:JSON.stringify(body)}),
  finish:(id:string)=>request<any>(`/debates/${id}/finish`,{method:'POST'}),
  pause:(id:string)=>request<any>(`/debates/${id}/pause`,{method:'POST'}),
  resume:(id:string)=>request<any>(`/debates/${id}/resume`,{method:'POST'}),
  evolve:(project_id:string)=>request<any>('/evolution/runs',{method:'POST',headers:jsonHeaders,body:JSON.stringify({project_id,games:2})}),
}
