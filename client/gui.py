from __future__ import annotations

import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox, ttk

import standalone_engine as engine
import runtime_bootstrap
from fast_server_pool import endpoints, rank

APP = "Findupto VPN"
VERSION = engine.APP_VERSION
FAST_LIMIT_MS = 250
PROBE_TIMEOUT = 1.2
BG = "#0a0d14"; PANEL = "#111722"; PANEL_2 = "#151c29"; BORDER = "#273246"
TEXT = "#f5f7fb"; MUTED = "#8f9aae"; ACCENT = "#7c5cff"; ACCENT_2 = "#9a82ff"
SUCCESS = "#31d6a5"; WARNING = "#ffbf69"; DANGER = "#ff6b81"; CYAN = "#5ddcff"

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP} {VERSION}")
        self.geometry(f"{max(980,min(1500,self.winfo_screenwidth()-55))}x{max(700,min(940,self.winfo_screenheight()-70))}")
        self.minsize(980,700); self.configure(bg=BG); self.events=queue.Queue(); self.servers=[]
        self.process=self.tmp=self.current_log=None; self.busy=False; self.cancel_event=threading.Event()
        self._configure_styles(); self._build(); self.after(100,self._pump); self.refresh()

    def _configure_styles(self):
        s=ttk.Style(self)
        try:s.theme_use("clam")
        except tk.TclError:pass
        s.configure("TFrame",background=BG); s.configure("TLabel",background=BG,foreground=TEXT,font=("Segoe UI",10))
        s.configure("Title.TLabel",background=BG,foreground=TEXT,font=("Segoe UI",25,"bold")); s.configure("Sub.TLabel",background=BG,foreground=MUTED,font=("Segoe UI",10))
        s.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=38,borderwidth=0,font=("Segoe UI",10))
        s.configure("Treeview.Heading",background=PANEL_2,foreground=MUTED,relief="flat",font=("Segoe UI",9,"bold"))
        s.map("Treeview",background=[("selected","#252d42")],foreground=[("selected",TEXT)])
        s.configure("TCheckbutton",background=PANEL,foreground=TEXT,font=("Segoe UI",9)); s.map("TCheckbutton",background=[("active",PANEL)])

    def _button(self,p,text,cmd,kind="secondary"):
        palette={"primary":(ACCENT,"white",ACCENT_2),"success":(SUCCESS,BG,"#50e7bb"),"danger":(DANGER,BG,"#ff8da0"),"secondary":(PANEL_2,TEXT,"#202a3b"),"ghost":(BG,MUTED,PANEL_2)}
        bg,fg,active=palette[kind]
        return tk.Button(p,text=text,command=cmd,bg=bg,fg=fg,activebackground=active,activeforeground=fg,relief="flat",bd=0,highlightthickness=1,highlightbackground=BORDER,cursor="hand2",font=("Segoe UI",10,"bold"),padx=15,pady=9)

    def _card(self,p): return tk.Frame(p,bg=PANEL,highlightthickness=1,highlightbackground=BORDER)

    def _build(self):
        header=ttk.Frame(self,padding=(28,20,28,10)); header.pack(fill="x")
        tk.Label(header,text="F",bg=ACCENT,fg="white",font=("Segoe UI",15,"bold"),width=3,pady=7).pack(side="left",padx=(0,12))
        brand=ttk.Frame(header); brand.pack(side="left"); ttk.Label(brand,text=APP,style="Title.TLabel").pack(anchor="w"); ttk.Label(brand,text="PRIVATE • FAST • VERIFIED",style="Sub.TLabel").pack(anchor="w")
        self.status=tk.StringVar(value="Preparing instant-connect pool…")
        tk.Label(header,textvariable=self.status,bg=PANEL,fg=MUTED,padx=15,pady=9,font=("Segoe UI",9,"bold")).pack(side="right")

        filters=self._card(self); filters.pack(fill="x",padx=28,pady=(4,10))
        tk.Label(filters,text="QUICK FILTERS",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left",padx=(15,8),pady=11)
        self.fast_only=tk.BooleanVar(value=True); self.available_only=tk.BooleanVar(value=True); self.auto_connect=tk.BooleanVar(value=False)
        ttk.Checkbutton(filters,text="Fast",variable=self.fast_only,command=self._render).pack(side="left",padx=5); ttk.Checkbutton(filters,text="Available",variable=self.available_only,command=self._render).pack(side="left",padx=5)
        self.country=tk.StringVar(value="All"); self.city=tk.StringVar(value="All"); self.source=tk.StringVar(value="All")
        for label,var in (("COUNTRY",self.country),("CITY",self.city),("SOURCE",self.source)):
            tk.Label(filters,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left",padx=(14,4)); cb=ttk.Combobox(filters,textvariable=var,state="readonly",width=13); cb.pack(side="left"); cb.bind("<<ComboboxSelected>>",lambda e:self._render()); setattr(self,label.lower()+"_combo",cb)
        tk.Label(filters,text="MAX PING",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left",padx=(14,4))
        self.max_ping=tk.IntVar(value=250); sp=ttk.Spinbox(filters,from_=50,to=2000,increment=25,width=6,textvariable=self.max_ping,command=self._render); sp.pack(side="left"); tk.Label(filters,text="ms",bg=PANEL,fg=MUTED).pack(side="left",padx=(3,10))
        ttk.Checkbutton(filters,text="Auto Connect",variable=self.auto_connect,command=self._auto_connect_changed).pack(side="left",padx=5)

        stats=tk.Frame(self,bg=BG); stats.pack(fill="x",padx=28,pady=(0,10)); self.stat_cards={}
        for key,label in (("shown","SHOWN"),("available","AVAILABLE"),("fast","FAST"),("pool","QUICK POOL"),("tested","TESTED")):
            c=self._card(stats); c.pack(side="left",fill="x",expand=True,padx=(0,7)); v=tk.StringVar(value="0"); tk.Label(c,textvariable=v,bg=PANEL,fg=TEXT,font=("Segoe UI",19,"bold")).pack(anchor="w",padx=13,pady=(8,0)); tk.Label(c,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=13,pady=(0,9)); self.stat_cards[key]=v

        quick=self._card(self); quick.pack(fill="x",padx=28,pady=(0,10)); top=tk.Frame(quick,bg=PANEL); top.pack(fill="x",padx=14,pady=(10,4)); tk.Label(top,text="⚡ ONE-CLICK FAST SERVERS",bg=PANEL,fg=TEXT,font=("Segoe UI",12,"bold")).pack(side="left"); tk.Label(top,text="LIVE VERIFIED",bg=PANEL,fg=SUCCESS,font=("Segoe UI",8,"bold")).pack(side="right")
        self.quick_frame=tk.Frame(quick,bg=PANEL); self.quick_frame.pack(fill="x",padx=10,pady=(2,12))

        body=self._card(self); body.pack(fill="both",expand=True,padx=28,pady=(0,10)); top=tk.Frame(body,bg=PANEL); top.pack(fill="x",padx=15,pady=10); tk.Label(top,text="FAST SERVER LOUNGE",bg=PANEL,fg=TEXT,font=("Segoe UI",12,"bold")).pack(side="left"); self.speed_status=tk.StringVar(value="Live probing…"); tk.Label(top,textvariable=self.speed_status,bg=PANEL,fg=SUCCESS,font=("Segoe UI",9,"bold")).pack(side="right")
        frame=tk.Frame(body,bg=PANEL); frame.pack(fill="both",expand=True,padx=10,pady=(0,10)); cols=("status","country","city","host","ips","ping","speed","source"); self.tree=ttk.Treeview(frame,columns=cols,show="headings",selectmode="browse")
        widths=(100,105,110,190,210,75,90,100)
        for col,w in zip(cols,widths):self.tree.heading(col,text=col.upper());self.tree.column(col,width=w,minwidth=55,anchor="w")
        y=ttk.Scrollbar(frame,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set); self.tree.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)

        bar=tk.Frame(self,bg=BG);bar.pack(fill="x",padx=28,pady=(0,18));self.refresh_btn=self._button(bar,"↻  Refresh Fast Pool",self.refresh);self.refresh_btn.pack(side="left");self.best_btn=self._button(bar,"✦  Connect Fastest",self.best,"primary");self.best_btn.pack(side="left",padx=8);self.sel_btn=self._button(bar,"➜  Connect Selected",self.selected);self.sel_btn.pack(side="left");self._button(bar,"◉ Diagnostics",self.open_log,"ghost").pack(side="left",padx=8);self._button(bar,"■ Disconnect",self.disconnect,"danger").pack(side="right")

    def _set_busy(self,v):
        self.busy=v; state="disabled" if v else "normal"
        for b in (self.refresh_btn,self.best_btn,self.sel_btn):b.configure(state=state)

    def _auto_connect_changed(self):
        if self.auto_connect.get() and not self.busy:self.best()

    @staticmethod
    def _probe(server):
        eps=endpoints(server); best=None; best_host=None
        for ep in eps[:8]:
            ports=[ep.port] if ep.port else ([443,80,53] if server.get("kind")=="gate" else [443,80])
            for port in ports:
                started=time.monotonic()
                try:
                    with socket.create_connection((ep.host,port),timeout=PROBE_TIMEOUT):
                        latency=(time.monotonic()-started)*1000
                        if best is None or latency<best:best,best_host=latency,ep.host
                except OSError:continue
        if best is None:return dict(server,available=False,live_ping=9999,ips=[e.host for e in eps])
        return dict(server,available=True,live_ping=best,ping=best,ip=best_host,host=server.get("host") or best_host,ips=[e.host for e in eps],rank=float(server.get("rank",0))+max(0,500-best))

    def refresh(self):
        if self.busy:return
        self.cancel_event.clear();self._set_busy(True);self.status.set("Scanning 100+ endpoints for instant-connect servers…");threading.Thread(target=self._discover_worker,daemon=True).start()

    def _discover_worker(self):
        try:
            data=engine.discover(10);tested=[]
            with ThreadPoolExecutor(max_workers=32,thread_name_prefix="vpn-probe") as pool:
                futures=[pool.submit(self._probe,s) for s in data[:150]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set():break
                    tested.append(f.result())
            tested.sort(key=lambda s:(not s.get("available"),s.get("live_ping",9999),-float(s.get("speed",0) or 0),-float(s.get("rank",0) or 0)))
            self.events.put(("servers",tested,f"Fast pool ready • {len(tested)} servers tested"))
        except Exception as exc:self.events.put(("error",None,f"Server discovery failed: {exc}"))

    def _eligible(self):
        try:limit=max(50,int(self.max_ping.get()))
        except Exception:limit=FAST_LIMIT_MS
        items=[s for s in self.servers if (not self.available_only.get() or s.get("available")) and (not self.fast_only.get() or float(s.get("live_ping",9999))<=limit)]
        for key,var in (("country",self.country),("city",self.city),("source",self.source)):
            if var.get()!="All":items=[s for s in items if str(s.get(key,""))==var.get()]
        return rank(items,limit,False,False)

    def _update_combos(self):
        for key,combo in (("country",self.country_combo),("city",self.city_combo),("source",self.source_combo)):
            vals=sorted({str(s.get(key,"")) for s in self.servers if s.get(key)})
            combo["values"]=["All"]+vals
            if combo.get() not in combo["values"]:combo.set("All")

    def _render_quick(self,items):
        for w in self.quick_frame.winfo_children():w.destroy()
        for s in items[:8]:
            ips=s.get("ips") or [s.get("ip") or s.get("host","")]; name=s.get("city") or s.get("country") or s.get("host","Server"); ping=float(s.get("live_ping",9999))
            card=tk.Frame(self.quick_frame,bg=PANEL_2,highlightthickness=1,highlightbackground="#303b55");card.pack(side="left",fill="x",expand=True,padx=4)
            tk.Label(card,text=f"● {name}",bg=PANEL_2,fg=SUCCESS,font=("Segoe UI",9,"bold")).pack(anchor="w",padx=9,pady=(7,0));tk.Label(card,text=f"{ping:.0f} ms  •  {len(ips)} IPs",bg=PANEL_2,fg=TEXT,font=("Segoe UI",9)).pack(anchor="w",padx=9)
            tk.Label(card,text="  ".join(str(x) for x in ips[:3]),bg=PANEL_2,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",padx=9,pady=(0,5));tk.Button(card,text="CONNECT",command=lambda x=s:self._connect([x]),bg=ACCENT,fg="white",relief="flat",bd=0,cursor="hand2",font=("Segoe UI",8,"bold"),padx=8,pady=5).pack(anchor="e",padx=8,pady=(0,7))

    def _render(self):
        visible=self._eligible();self.tree.delete(*self.tree.get_children());index={id(s):i for i,s in enumerate(self.servers)}
        for s in visible:
            ping=float(s.get("live_ping",9999));ips=s.get("ips") or [s.get("ip") or s.get("host","")]
            self.tree.insert("","end",iid=str(index[id(s)]),values=("● FAST" if s.get("available") and ping<=FAST_LIMIT_MS else "● ONLINE",s.get("country",""),s.get("city",""),s.get("host","") or s.get("ip",""),", ".join(str(x) for x in ips[:4]),"—" if ping>=9999 else f"{ping:.0f} ms",f"{float(s.get('speed',0) or 0):.1f} Mbps" if s.get("speed") else "—",s.get("source","")))
        available=sum(bool(s.get("available")) for s in self.servers);fast=sum(bool(s.get("available")) and float(s.get("live_ping",9999))<=FAST_LIMIT_MS for s in self.servers);quick=len(self._eligible()[:8])
        self.stat_cards["shown"].set(str(len(visible)));self.stat_cards["available"].set(str(available));self.stat_cards["fast"].set(str(fast));self.stat_cards["pool"].set(str(quick));self.stat_cards["tested"].set(str(len(self.servers)));self._render_quick(visible);self._update_combos()

    def best(self):
        candidates=self._eligible()
        if not candidates:messagebox.showwarning(APP,"No fast available server matches the filters. Refresh or widen MAX PING.");return
        self._connect(candidates[:24])

    def selected(self):
        sel=self.tree.selection()
        if not sel:return messagebox.showwarning(APP,"Select a server first.")
        try:s=self.servers[int(sel[0])]
        except (ValueError,IndexError):return messagebox.showwarning(APP,"Server is no longer in the live pool.")
        if self.available_only.get() and not s.get("available"):return messagebox.showwarning(APP,"This server is not available.")
        self._connect([s])

    def _connect(self,candidates):
        if self.busy or not candidates:return
        self.cancel_event.clear();self._set_busy(True);self.status.set(f"✦ Trying {len(candidates)} verified fast servers…");threading.Thread(target=self._connect_worker,args=(candidates,),daemon=True).start()

    @staticmethod
    def _stop_process(process,tmp=None):
        if process is not None:
            try:process.terminate();process.wait(timeout=3)
            except Exception:
                try:process.kill()
                except Exception:pass
        if tmp:shutil.rmtree(tmp,ignore_errors=True)

    def _connect_worker(self,candidates):
        errors=[]
        try:baseline=engine.public_ip(6)
        except Exception:baseline=None
        for server in candidates:
            if self.cancel_event.is_set() or self.process is not None:return
            try:
                self.events.put(("status",None,f"✦ {server.get('host') or server.get('ip')} • {server.get('live_ping',0):.0f} ms • connecting…"));runtime_bootstrap.install_bundled_drivers();process,tmp,logfile=engine.connect(server,45)
                if self.cancel_event.is_set():self._stop_process(process,tmp);return
                if process.poll() is not None:raise RuntimeError("VPN process exited after startup")
                ip=engine.verify_tunnel(baseline,10);self.process,self.tmp,self.current_log=process,tmp,logfile
                self.events.put(("connected",None,f"CONNECTED • {server.get('host') or server.get('ip')} • {server.get('live_ping',0):.0f} ms • IP {ip}"));return
            except Exception as exc:errors.append(f"{server.get('host') or server.get('ip')}: {exc}")
        if not self.cancel_event.is_set():self.events.put(("error",None,"No verified fast server connected.\n\n"+"\n".join(errors[:12])))

    def disconnect(self):
        self.cancel_event.set();process,tmp=self.process,self.tmp;self.process=self.tmp=self.current_log=None
        if process is not None:self._stop_process(process,tmp)
        elif tmp:shutil.rmtree(tmp,ignore_errors=True)
        if hasattr(self,"status"):self.status.set("Disconnected")
        if hasattr(self,"refresh_btn"):self._set_busy(False)

    @staticmethod
    def _open_path(path):
        try:
            if os.name=="nt":os.startfile(str(path))
            elif sys.platform=="darwin":subprocess.Popen(["open",str(path)])
            else:subprocess.Popen(["xdg-open",str(path)])
            return True
        except Exception:return False

    def open_log(self):
        engine.ROOT.mkdir(parents=True,exist_ok=True);engine.LOG.touch(exist_ok=True)
        if not self._open_path(engine.LOG):messagebox.showinfo(APP,f"Diagnostic log:\n{engine.LOG}")

    def _pump(self):
        try:
            while True:
                kind,data,msg=self.events.get_nowait()
                if kind=="servers":self.servers=data or [];self._render();self._set_busy(False);self.status.set(msg);self.speed_status.set("● LIVE • fast endpoints verified");self._auto_connect_changed()
                elif kind=="status":self.status.set(msg)
                elif kind=="connected":self._set_busy(False);self.status.set(msg);self.speed_status.set("● CONNECTED • tunnel verified")
                elif kind=="error":self._set_busy(False);self.status.set("Connection unavailable");self.speed_status.set("● OFFLINE");messagebox.showerror(APP,msg)
        except queue.Empty:pass
        self.after(100,self._pump)

    def destroy(self):self.disconnect();super().destroy()

if __name__=="__main__":App().mainloop()
