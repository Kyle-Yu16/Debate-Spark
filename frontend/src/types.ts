export type Stance = '正方' | '反方'
export interface Project { id:string; topic:string; stance:Stance; status:string; created_at:string; updated_at:string; workspace?:Workspace }
export interface Evidence { id:string; title:string; claim:string; url:string; domain:string; date:string; credibility:string; scope:string; counter:string }
export interface Argument { id:string; stance:Stance; title:string; claim:string; warrant:string; evidence_ids:string[]; locked:boolean; status:string }
export interface Insight { lens:string; idea:string; score:number; support:string }
export interface Workspace {
  topic:string; stance:Stance;
  analysis:{keywords:string[]; definitions:string[]; conflicts:string[]; criterion:string; burdens:Record<string,string>};
  arguments:Argument[]; evidence:Evidence[]; matrix:{our:string;attack:string;response:string}[];
  insights:Insight[]; drafts:Record<string,string|string[]>; warnings:string[]
}
export interface Turn { id:string; speaker:string; stance:Stance; stage:string; content:string; meta:Record<string,any>; created_at:string }
export interface Evaluation { winner:string; scores:Record<string,Record<string,number>>; turning_points:string[]; missed_responses:string[]; highlights:{quote:string;reason:string;stance:string}[]; exercises:string[]; summary:string }
export interface Debate { id:string; project_id:string; mode:'human'|'arena'; user_stance:Stance; difficulty:string; status:string; state:any; turns?:Turn[]; evaluation?:Evaluation }
export interface WorkspaceVersion { id:string; label:string; created_at:string }
export interface DebateHistory extends Debate { turn_count:number; created_at:string; updated_at:string }
export interface ProjectHistory { workspace_versions:WorkspaceVersion[]; debates:DebateHistory[] }
