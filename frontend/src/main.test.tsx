import {afterEach,describe,it,expect,vi} from 'vitest'
import {render,screen,cleanup} from '@testing-library/react'
import {App} from './main'

afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear()})

describe('dashboard',()=>{
 it('requires an administrator token before showing data',()=>{
  sessionStorage.clear();render(<App/>);
  expect(screen.getByText('Connect to your local control plane')).toBeTruthy()
 })
 it('shows when automatic restart is armed instead of labeling it read-only',async()=>{
  sessionStorage.setItem('healops-token','test-only')
  vi.stubGlobal('fetch',vi.fn(async (path:string)=>({ok:true,json:async()=>{
   if(path.endsWith('/dashboard'))return {total:1,healthy:1,unhealthy:0,monitor_online:true,open_incidents:0,recovered:0,failed:0}
   if(path.endsWith('/settings'))return {managed_containers:['pw3-attendance'],auto_restart:true,restart_limit:2,llm_configured:false,github_connected:false,mode:'policy'}
   return []
  }})))
  render(<App/>)
  expect(await screen.findByText('MONITOR ONLINE · AUTO-RESTART ARMED')).toBeTruthy()
 })
})
