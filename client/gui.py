from __future__ import annotations
import os,queue,shutil,threading
import tkinter as tk
from tkinter import messagebox,ttk
import vpn_engine as engine
APP='Findupto VPN';VERSION='9.1.0'
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title(f'{APP} {VERSION}');self.geometry('1120x700');self.minsize(900,560);self.events=queue.Queue();self.servers=[];self.process=None;self.tmp=None;self.current_log=None;self.busy=False;self._build();self.after(100,self._pump);self.refresh()
 def _build(self):
  head=ttk.Frame(self,padding=14);head.pack(fill='x');ttk.Label(head,text=APP,font=('Segoe UI',20,'bold')).pack(side='left');ttk.Label(head,text=f'  Smart Multi-Source {VERSION}').pack(side='left',pady=7)
  self.status=tk.StringVar(value='Starting...');ttk.Label(self,textvariable=self.status,padding=(14,0,14,10)).pack(fill='x')
  frame=ttk.Frame(self,padding=(14,0,14,0));frame.pack(fill='both',expand=True);cols=('country','city','host','ping','speed','source');self.tree=ttk.Treeview(frame,columns=cols,show='headings')
  for col,width in zip(cols,(140,150,260,90,110,120)):self.tree.heading(col,text=col.title());self.tree.column(col,width=width,anchor='w')
  y=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=y.set);self.tree.pack(side='left',fill='both',expand=True);y.pack(side='right',fill='y')
  bar=ttk.Frame(self,padding=14);bar.pack(fill='x');self.refresh_btn=ttk.Button(bar,text='Refresh',command=self.refresh);self.refresh_btn.pack(side='left');self.best_btn=ttk.Button(bar,text='Connect Best',command=self.best);self.best_btn.pack(side='left',padx=7);self.sel_btn=ttk.Button(bar,text='Connect Selected',command=self.selected);self.sel_btn.pack(side='left');ttk.Button(bar,text='Open Diagnostic Log',command=self.open_log).pack(side='left',padx=7);ttk.Button(bar,text='Open OpenVPN Logs',command=self.open_openvpn_logs).pack(side='left');ttk.Button(bar,text='Disconnect',command=self.disconnect).pack(side='right')
 def _set_busy(self,value):
  self.busy=value;state='disabled' if value else 'normal'
  for b in (self.refresh_btn,self.best_btn,self.sel_btn):b.configure(state=state)
 def refresh(self):
  if self.busy:return
  self._set_busy(True);self.status.set('Discovering cached + live VPN sources...');engine.log('UI REFRESH');threading.Thread(target=self._discover_worker,daemon=True).start()
 def _discover_worker(self):
  try:self.events.put(('servers',engine.discover(12), 'Live catalog ready; automatic failover is enabled'))
  except Exception as exc:engine.log(f'DISCOVERY FATAL {type(exc).__name__}: {exc}');self.events.put(('error',None,f'Discovery failed: {exc}\n\n{engine.LOG}'))
 def _render(self,data):
  self.servers=data;self.tree.delete(*self.tree.get_children())
  for i,s in enumerate(data):
   ping='-' if s.get('ping',9999)>=9999 else f"{s['ping']:.0f} ms";speed='-' if not s.get('speed') else f"{s['speed']:.1f} Mbps";self.tree.insert('','end',iid=str(i),values=(s.get('country',''),s.get('city',''),s.get('host',''),ping,speed,s.get('source','')))
 def best(self):
  if not self.servers:messagebox.showwarning(APP,'No candidates. Refresh first.');return
  gate=[s for s in self.servers if s.get('kind')=='gate'][:8];book=[s for s in self.servers if s.get('kind')=='book'];self._connect(gate+book)
 def selected(self):
  sel=self.tree.selection()
  if not sel:messagebox.showwarning(APP,'Select a server first.');return
  self._connect([self.servers[int(sel[0])]])
 def _connect(self,candidates):
  if self.busy:return
  self._set_busy(True);self.status.set(f'Testing {len(candidates)} candidates; success requires a changed public IP...');threading.Thread(target=self._connect_worker,args=(candidates,),daemon=True).start()
 def _connect_worker(self,candidates):
  errors=[]
  try:baseline=engine.public_ip(6);engine.log(f'CONNECT BASELINE public_ip={baseline}')
  except Exception as exc:baseline=None;engine.log(f'CONNECT BASELINE unavailable: {type(exc).__name__}: {exc}')
  for server in candidates:
   if self.process is not None:return
   try:
    self.events.put(('status',None,f"Trying {server['host']} ({server['source']})..."));process,tmp,logfile=engine.connect(server,50)
    try:ip=engine.verify_tunnel(baseline,8)
    except Exception:
     try:process.terminate()
     except Exception:pass
     shutil.rmtree(tmp,ignore_errors=True);raise
    self.process,self.tmp,self.current_log=process,tmp,logfile;self.events.put(('connected',None,f"CONNECTED — {server['host']} — verified public IP {ip}"));return
   except Exception as exc:
    msg=f"{server['host']}: {exc}";errors.append(msg);engine.log(msg)
  self.events.put(('error',None,'No candidate connected successfully.\n\n'+'\n'.join(errors[:20])+f'\n\nDiagnostic log:\n{engine.LOG}\nOpenVPN logs:\n{engine.PROFILE_LOGS}'))
 def disconnect(self):
  p=self.process;self.process=None
  if p is not None:
   engine.log('DISCONNECT')
   try:p.terminate();p.wait(timeout=3)
   except Exception:
    try:p.kill()
    except Exception:pass
  if self.tmp:shutil.rmtree(self.tmp,ignore_errors=True);self.tmp=None
  self.current_log=None
  if hasattr(self,'status'):self.status.set('Disconnected')
 def open_log(self):
  engine.ROOT.mkdir(parents=True,exist_ok=True);engine.LOG.touch(exist_ok=True);engine.log('DIAGNOSTIC LOG OPENED')
  try:os.startfile(engine.LOG)
  except Exception:messagebox.showinfo(APP,f'Diagnostic log:\n{engine.LOG}')
 def open_openvpn_logs(self):
  engine.PROFILE_LOGS.mkdir(parents=True,exist_ok=True)
  try:os.startfile(engine.PROFILE_LOGS)
  except Exception:messagebox.showinfo(APP,f'OpenVPN logs:\n{engine.PROFILE_LOGS}')
 def _pump(self):
  try:
   while True:
    typ,data,message=self.events.get_nowait()
    if typ=='servers':self._render(data);self._set_busy(False);self.status.set(message)
    elif typ=='status':self.status.set(message)
    elif typ=='connected':self._set_busy(False);self.status.set(message)
    elif typ=='error':self._set_busy(False);self.status.set('Failed — see diagnostics');messagebox.showerror(APP,message)
  except queue.Empty:pass
  self.after(100,self._pump)
 def destroy(self):self.disconnect();super().destroy()
if __name__=='__main__':App().mainloop()
