// Official Platform source. The Agent Center static asset is generated from this file.
export const MODULES=Object.freeze([
 {id:'finance',name:'Finanzas',color:'blue',icon:'finance',href:'https://finanzas-dev.uonify.com/'},
 {id:'ecommerce',name:'Ecommerce',color:'violet',icon:'sales',href:'https://ecom-dev.uonify.com/'},
 {id:'inventory',name:'Inventario',color:'teal',icon:'inventory'},
 {id:'transport',name:'Transporte',color:'rose',icon:'transport'},
 {id:'crm',name:'CRM',color:'rose',icon:'people'},
 {id:'marketing',name:'Marketing',color:'orange',icon:'marketing'},
 {id:'services',name:'Servicios',color:'teal',icon:'services'},
 {id:'agents',name:'Centro de Agentes',color:'violet',icon:'agents',href:'https://agentes-dev.uonify.com/'},
 {id:'studio',name:'Estudio',color:'slate',icon:'studio'},
 {id:'productivity',name:'Productividad',color:'indigo',icon:'productivity'},
 {id:'pos',name:'Punto de venta',color:'orange',icon:'pos'},
].map(Object.freeze));

const paths={
 finance:'<path d="M4 20h16M6 16v-4m6 4V8m6 8V4m-13 4 6-5 4 2 4-3"/>',
 sales:'<path d="M3 4h2l2 12h12l2-9H6"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
 inventory:'<path d="M3 21V9l9-6 9 6v12M7 21V11h10v10M3 21h18M7 15h10m-10 3h10m-7-7v10m4-10v10"/>',
 transport:'<path d="M3 5h11v12H3V5Zm11 5h4l3 4v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
 people:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-17a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v3"/>',
 marketing:'<path d="m4 10 13-5v14L4 14v-4Zm13 0h4v4h-4M7 15l2 6h4l-2-5"/>',
 services:'<path d="m14 5 5 5M9 10l-6 6a3 3 0 0 0 5 5l6-6M14 3a6 6 0 0 0-6 8l5 5a6 6 0 0 0 8-6l-4 3-4-4 3-4-2-2Z"/>',
 agents:'<rect x="4" y="7" width="16" height="14" rx="4"/><path d="M12 7V3M2 12v5m20-5v5M9 16h6"/><circle cx="9" cy="12" r=".5"/><circle cx="15" cy="12" r=".5"/>',
 studio:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 9 5 3-5 3V9ZM3 8h18"/>',
 productivity:'<rect x="4" y="4" width="16" height="17" rx="3"/><path d="M8 3v3m8-3v3M4 10h16m-12 5 3 3 5-5"/>',
 pos:'<rect x="3" y="3" width="18" height="12" rx="2"/><path d="M9 15v5m6-5v5M6 21h12M7 7h5m-5 4h9"/>',
};
const styles=`
 :host{display:inline-flex;position:relative;flex:none;font-family:Inter,system-ui,sans-serif;font-size:14px;line-height:1.5;color:#374151;--border:#e8edf3;--muted:#667085}
 *{box-sizing:border-box}[hidden]{display:none!important}button{font:inherit;cursor:pointer;border:0;background:transparent;color:var(--muted)}
 .trigger,.close{display:grid;place-items:center;padding:0;border-radius:50%}.trigger{width:42px;height:42px}.trigger svg{width:23px;height:23px;fill:currentColor}
 .trigger:hover,.trigger[aria-expanded=true],.close:hover{background:#edf3fc;color:#2563b8}button:focus-visible,a:focus-visible{outline:2px solid #2563eb;outline-offset:3px}
 .panel{position:absolute;right:0;top:calc(100% + 14px);z-index:1000;width:350px;max-width:calc(100vw - 32px);max-height:calc(100dvh - 110px);overflow:auto;overscroll-behavior:contain;padding:20px;background:#fff;border:1px solid var(--border);border-radius:22px;box-shadow:0 12px 40px #253c6521;text-align:left}
 .heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.heading strong{font-size:15px;font-weight:500}.heading p{margin:4px 0 0;font-size:12px;color:var(--muted)}.close{width:30px;height:30px;font-size:24px;flex:none}
 .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.tile{display:flex;flex-direction:column;align-items:center;gap:9px;min-width:0;padding:14px 5px 12px;border-radius:14px;text-decoration:none;color:#374151;font-size:12px;font-weight:400;text-align:center;line-height:1.4}
 a.tile:hover{background:#f4f7fc}.current{background:#f0f6ff}.tile small{font-size:10px;color:var(--muted);margin-top:-5px}.icon{display:grid;place-items:center;width:48px;height:48px;border-radius:15px;background:#edf4ff;color:#3473cf}.icon svg{width:28px;height:28px}
 .violet{background:#f0edfc;color:#7860c5}.teal{background:#e8f6f3;color:#278575}.orange{background:#fff1e6;color:#b66a2d}.rose{background:#fbeef3;color:#b65f83}.slate{background:#edf1f6;color:#60718b}.indigo{background:#edf0ff;color:#5e6cba}
 .note{margin:18px 0 0;padding-top:14px;border-top:1px solid var(--border);font-size:12px;line-height:1.6;color:var(--muted)}
 @media(max-width:600px){.panel{position:fixed;right:16px;top:84px;width:350px;max-height:calc(100dvh - 100px)}.grid{gap:4px}}
`;
const svg=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;

if(typeof window!=='undefined'&&!window.customElements.get('mastererp-module-launcher')){
 class ModuleLauncher extends HTMLElement{
  static observedAttributes=['current-app'];
  constructor(){
   super();this.attachShadow({mode:'open'});this.opened=false;
   this.outside=event=>{if(!event.composedPath().includes(this))this.close();};
   this.escape=event=>{if(event.key==='Escape'){event.preventDefault();this.close(true);}};
  }
  connectedCallback(){this.render();}
  disconnectedCallback(){this.stopListening();}
  attributeChangedCallback(){if(this.isConnected)this.render();}
  stopListening(){document.removeEventListener('pointerdown',this.outside);document.removeEventListener('focusin',this.outside);document.removeEventListener('keydown',this.escape);}
  close(focus=false){
   this.opened=false;this.stopListening();const trigger=this.shadowRoot.querySelector('.trigger'),panel=this.shadowRoot.querySelector('.panel');
   trigger?.setAttribute('aria-expanded','false');if(panel)panel.hidden=true;if(focus)trigger?.focus();
  }
  toggle(){
   if(this.opened){this.close();return;}this.opened=true;this.shadowRoot.querySelector('.panel').hidden=false;this.shadowRoot.querySelector('.trigger').setAttribute('aria-expanded','true');
   document.addEventListener('pointerdown',this.outside);document.addEventListener('focusin',this.outside);document.addEventListener('keydown',this.escape);
  }
  render(){
   this.close();const current=this.getAttribute('current-app');
   // Only fixed catalogue constants are rendered; no remote code or user-provided HTML.
   this.shadowRoot.innerHTML=`<style>${styles}</style>
    <button class="trigger" type="button" aria-label="Abrir módulos" title="Módulos de MasterERP" aria-expanded="false" aria-controls="module-panel"><svg viewBox="0 0 24 24" aria-hidden="true">${[5,12,19].flatMap(y=>[5,12,19].map(x=>`<circle cx="${x}" cy="${y}" r="1.6"/>`)).join('')}</svg></button>
    <section id="module-panel" class="panel" aria-label="Módulos de MasterERP" hidden><div class="heading"><div><strong>Tu espacio de trabajo</strong><p>MasterERP + Uonify</p></div><button type="button" class="close" aria-label="Cerrar módulos">×</button></div>
     <div class="grid">${MODULES.map(module=>{
      const active=module.id===current,content=`<span class="icon ${module.color}">${svg(module.icon)}</span><span>${module.name}</span><small>${active?'Estás aquí':module.href?'Abrir aplicación':'Pendiente'}</small>`;
      return active?`<div class="tile current" aria-current="true">${content}</div>`:module.href?`<a class="tile" href="${module.href}">${content}</a>`:`<div class="tile" aria-disabled="true">${content}</div>`;
     }).join('')}</div><p class="note">Cada aplicación valida tu acceso. Los módulos pendientes todavía no están disponibles.</p></section>`;
   const trigger=this.shadowRoot.querySelector('.trigger');trigger.addEventListener('click',()=>this.toggle());
   trigger.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();if(!this.opened)this.toggle();this.shadowRoot.querySelector('.grid a')?.focus();}});
   this.shadowRoot.querySelector('.close').addEventListener('click',()=>this.close(true));
  }
 }
 window.customElements.define('mastererp-module-launcher',ModuleLauncher);
}
