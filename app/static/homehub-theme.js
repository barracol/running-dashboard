(()=>{
  const COOKIE='homehub_theme';
  const read=()=>document.cookie.split('; ').find(x=>x.startsWith(`${COOKIE}=`))?.split('=')[1];
  const preferred=()=>read()||'dark';
  const apply=theme=>{
    const value=theme==='light'?'light':'dark';
    document.documentElement.dataset.homehubTheme=value;
    document.documentElement.style.colorScheme=value;
    document.querySelectorAll('.homehub-theme-control').forEach(button=>{
      button.setAttribute('aria-label',value==='light'?'Passa al tema scuro':'Passa al tema chiaro');
      button.querySelector('.homehub-theme-control-label').textContent=value==='light'?'Light':'Dark';
    });
    document.dispatchEvent(new CustomEvent('homehub-theme',{detail:{theme:value}}));
  };
  const set=theme=>{
    const value=theme==='light'?'light':'dark';
    document.cookie=`${COOKIE}=${value}; Path=/; Max-Age=31536000; SameSite=Lax`;
    apply(value);
  };
  const mount=()=>{
    if(document.querySelector('#theme-toggle,.homehub-theme-control')) return;
    const button=document.createElement('button');
    button.type='button';button.className='homehub-theme-control';
    button.innerHTML='<span class="homehub-theme-control-track"><span class="homehub-theme-control-thumb"></span></span><span class="homehub-theme-control-label"></span>';
    button.addEventListener('click',()=>set(preferred()==='light'?'dark':'light'));
    document.body.append(button);apply(preferred());
  };
  window.HomeHubTheme={get:preferred,set,apply,toggle:()=>set(preferred()==='light'?'dark':'light')};
  apply(preferred());
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',mount,{once:true}):mount();
})();
