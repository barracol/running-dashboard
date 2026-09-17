document.addEventListener('DOMContentLoaded',()=>{
  const params=new URLSearchParams(location.search),hub=new URL(location.href);hub.port=params.get('hub')||'8050';hub.pathname='/';hub.search='';hub.hash='';
  const existing=document.querySelector('.home-hub-link,.ui-home-hub,#hubLink,#hub,a.hub')||[...document.querySelectorAll('a')].find(link=>link.textContent.includes('Home Hub'));
  if(existing){existing.href=hub.toString();existing.setAttribute('aria-label','Torna alla Home Hub');existing.classList.add('ui-home-hub')}else{const link=document.createElement('a');link.className='ui-home-hub';link.href=hub.toString();link.textContent='⌂ Home Hub';link.setAttribute('aria-label','Torna alla Home Hub');document.body.append(link)}
  document.querySelectorAll('dialog').forEach(dialog=>{dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()})});
  document.querySelectorAll('.error,.message,.form-message').forEach(element=>{element.setAttribute('role','status');element.setAttribute('aria-live','polite')});
  if(!document.querySelector('meta[name="theme-color"]')){const meta=document.createElement('meta');meta.name='theme-color';meta.content=getComputedStyle(document.body).backgroundColor||'#07100d';document.head.append(meta)}
});
